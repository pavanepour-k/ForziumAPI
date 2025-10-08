use crate::compute::rayon_metrics;
use crate::error::ForziumError;
use rayon::prelude::*;
#[cfg(target_arch = "x86_64")]
use std::arch::x86_64::*;

fn validate_matrix(m: &[Vec<f64>]) -> Result<(usize, usize), ForziumError> {
    if m.is_empty() || m[0].is_empty() {
        return Err(ForziumError::Validation("empty tensor".into()));
    }
    let cols = m[0].len();
    if m.iter().any(|r| r.len() != cols) {
        return Err(ForziumError::Validation("ragged tensor".into()));
    }
    Ok((m.len(), cols))
}

fn validate_same_shape(a: &[Vec<f64>], b: &[Vec<f64>]) -> Result<(usize, usize), ForziumError> {
    let (rows_a, cols_a) = validate_matrix(a)?;
    let (rows_b, cols_b) = validate_matrix(b)?;
    if rows_a != rows_b || cols_a != cols_b {
        return Err(ForziumError::Validation("shape mismatch".into()));
    }
    Ok((rows_a, cols_a))
}

pub fn multiply(m: &[Vec<f64>], factor: f64) -> Result<Vec<Vec<f64>>, ForziumError> {
    validate_matrix(m)?;
    Ok(m.par_iter()
        .map(|r| {
            let _guard = rayon_metrics::track_task();
            r.par_iter().map(|v| v * factor).collect()
        })
        .collect())
}

pub fn add(m: &[Vec<f64>], addend: f64) -> Result<Vec<Vec<f64>>, ForziumError> {
    validate_matrix(m)?;
    Ok(m.par_iter()
        .map(|r| {
            let _guard = rayon_metrics::track_task();
            r.par_iter().map(|v| v + addend).collect()
        })
        .collect())
}

pub fn transpose(m: &[Vec<f64>]) -> Result<Vec<Vec<f64>>, ForziumError> {
    let (rows, cols) = validate_matrix(m)?;
    let mut out = vec![vec![0.0; rows]; cols];
    for (r, row) in m.iter().enumerate() {
        for (c, val) in row.iter().enumerate() {
            out[c][r] = *val;
        }
    }
    Ok(out)
}

pub fn matmul(a: &[Vec<f64>], b: &[Vec<f64>]) -> Result<Vec<Vec<f64>>, ForziumError> {
    let (_rows_a, cols_a) = validate_matrix(a)?;
    let (rows_b, cols_b) = validate_matrix(b)?;
    if cols_a != rows_b {
        return Err(ForziumError::Validation("shape mismatch".into()));
    }
    let out: Vec<Vec<f64>> = a
        .par_iter()
        .map(|row_a| {
            let _guard = rayon_metrics::track_task();
            let mut out_row = vec![0.0; cols_b];
            for (k, val_a) in row_a.iter().enumerate() {
                let row_b = &b[k];
                for (j, val_b) in row_b.iter().enumerate() {
                    out_row[j] += val_a * val_b;
                }
            }
            out_row
        })
        .collect();
    Ok(out)
}

pub fn simd_matmul(a: &[Vec<f64>], b: &[Vec<f64>]) -> Result<Vec<Vec<f64>>, ForziumError> {
    let (_rows_a, cols_a) = validate_matrix(a)?;
    let (rows_b, cols_b) = validate_matrix(b)?;
    if cols_a != rows_b {
        return Err(ForziumError::Validation("shape mismatch".into()));
    }
    let bt = transpose(b)?;
    let out: Vec<Vec<f64>> = a
        .par_iter()
        .map(|row_a| {
            let _guard = rayon_metrics::track_task();
            let mut out_row = vec![0.0; cols_b];
            #[cfg(target_arch = "x86_64")]
            unsafe {
                // SAFETY: We ensure row_a has at least k elements and bt_row has at least k elements
                // before dereferencing pointers. The loop bound `k + 2 <= cols_a` guarantees we don't
                // exceed bounds when loading 2 elements at a time. The `validate_matrix` function
                // ensures all vectors have the correct length, and `transpose` preserves the total
                // element count. The `_mm_loadu_pd` intrinsic can handle unaligned memory safely.
                for (bt_row, out_cell) in bt.iter().zip(out_row.iter_mut()) {
                    let mut k = 0;
                    let mut vsum = _mm_set1_pd(0.0);
                    while k + 2 <= cols_a {
                        let va = _mm_loadu_pd(row_a.as_ptr().add(k));
                        let vb = _mm_loadu_pd(bt_row.as_ptr().add(k));
                        let prod = _mm_mul_pd(va, vb);
                        vsum = _mm_add_pd(vsum, prod);
                        k += 2;
                    }
                    let mut buf = [0.0f64; 2];
                    _mm_storeu_pd(buf.as_mut_ptr(), vsum);
                    let mut sum = buf[0] + buf[1];
                    while k < cols_a {
                        sum += row_a[k] * bt_row[k];
                        k += 1;
                    }
                    *out_cell = sum;
                }
            }
            #[cfg(not(target_arch = "x86_64"))]
            {
                for (bt_row, out_cell) in bt.iter().zip(out_row.iter_mut()) {
                    let mut sum = 0.0;
                    for (val_a, val_b) in row_a.iter().zip(bt_row.iter()) {
                        sum += val_a * val_b;
                    }
                    *out_cell = sum;
                }
            }
            out_row
        })
        .collect();
    Ok(out)
}

pub fn elementwise_add(a: &[Vec<f64>], b: &[Vec<f64>]) -> Result<Vec<Vec<f64>>, ForziumError> {
    validate_same_shape(a, b)?;
    Ok(a.par_iter()
        .zip(b.par_iter())
        .map(|(row_a, row_b)| {
            let _guard = rayon_metrics::track_task();
            row_a
                .par_iter()
                .zip(row_b.par_iter())
                .map(|(val_a, val_b)| val_a + val_b)
                .collect()
        })
        .collect())
}

pub fn simd_elementwise_add(a: &[Vec<f64>], b: &[Vec<f64>]) -> Result<Vec<Vec<f64>>, ForziumError> {
    let (rows, cols) = validate_same_shape(a, b)?;
    let mut out = vec![vec![0.0; cols]; rows];
    #[cfg(target_arch = "x86_64")]
    unsafe {
        // SAFETY: We ensure a[r] and b[r] have at least c elements before dereferencing pointers.
        // The loop bound `c + 2 <= cols` guarantees we don't exceed bounds when loading 2 elements
        // at a time. The `validate_same_shape` function ensures all vectors have the same length.
        // The `_mm_loadu_pd` and `_mm_storeu_pd` intrinsics can handle unaligned memory safely.
        for r in 0..rows {
            let mut c = 0;
            while c + 2 <= cols {
                let va = _mm_loadu_pd(a[r].as_ptr().add(c));
                let vb = _mm_loadu_pd(b[r].as_ptr().add(c));
                let vc = _mm_add_pd(va, vb);
                _mm_storeu_pd(out[r].as_mut_ptr().add(c), vc);
                c += 2;
            }
            while c < cols {
                out[r][c] = a[r][c] + b[r][c];
                c += 1;
            }
        }
    }
    #[cfg(not(target_arch = "x86_64"))]
    {
        for (row_out, (row_a, row_b)) in out.iter_mut().zip(a.iter().zip(b.iter())) {
            for (val_out, (val_a, val_b)) in row_out.iter_mut().zip(row_a.iter().zip(row_b.iter()))
            {
                *val_out = val_a + val_b;
            }
        }
    }
    Ok(out)
}

pub fn hadamard(a: &[Vec<f64>], b: &[Vec<f64>]) -> Result<Vec<Vec<f64>>, ForziumError> {
    validate_same_shape(a, b)?;
    Ok(a.par_iter()
        .zip(b.par_iter())
        .map(|(row_a, row_b)| {
            let _guard = rayon_metrics::track_task();
            row_a
                .par_iter()
                .zip(row_b.par_iter())
                .map(|(val_a, val_b)| val_a * val_b)
                .collect()
        })
        .collect())
}

#[allow(clippy::needless_range_loop)]
pub fn conv2d(input: &[Vec<f64>], kernel: &[Vec<f64>]) -> Result<Vec<Vec<f64>>, ForziumError> {
    let (rows, cols) = validate_matrix(input)?;
    let (krows, kcols) = validate_matrix(kernel)?;
    if rows < krows || cols < kcols {
        return Err(ForziumError::Validation("kernel larger than input".into()));
    }
    let out_rows = rows - krows + 1;
    let out_cols = cols - kcols + 1;
    let mut out = vec![vec![0.0; out_cols]; out_rows];
    out.par_iter_mut().enumerate().for_each(|(r, out_row)| {
        let _guard = rayon_metrics::track_task();
        for c in 0..out_cols {
            let mut sum = 0.0;
            #[cfg(target_arch = "x86_64")]
            unsafe {
                // SAFETY: We ensure input[r + kr] has at least c + kc elements and kernel[kr] has at least
                // kc elements before dereferencing pointers. The loop bounds `r + kr < rows` and
                // `c + kc < cols` are guaranteed by the outer loop bounds and the convolution output
                // size calculation. The `_mm_loadu_pd` intrinsic can handle unaligned memory safely.
                for kr in 0..krows {
                    let mut kc = 0;
                    let mut vsum = _mm_set1_pd(0.0);
                    while kc + 2 <= kcols {
                        let inp = _mm_loadu_pd(input[r + kr].as_ptr().add(c + kc));
                        let ker = _mm_loadu_pd(kernel[kr].as_ptr().add(kc));
                        let prod = _mm_mul_pd(inp, ker);
                        vsum = _mm_add_pd(vsum, prod);
                        kc += 2;
                    }
                    let mut buf = [0.0f64; 2];
                    _mm_storeu_pd(buf.as_mut_ptr(), vsum);
                    sum += buf[0] + buf[1];
                    while kc < kcols {
                        sum += input[r + kr][c + kc] * kernel[kr][kc];
                        kc += 1;
                    }
                }
            }
            #[cfg(not(target_arch = "x86_64"))]
            {
                for kr in 0..krows {
                    for kc in 0..kcols {
                        sum += input[r + kr][c + kc] * kernel[kr][kc];
                    }
                }
            }
            out_row[c] = sum;
        }
    });
    Ok(out)
}

#[allow(clippy::needless_range_loop)]
pub fn max_pool2d(input: &[Vec<f64>], size: usize) -> Result<Vec<Vec<f64>>, ForziumError> {
    let (rows, cols) = validate_matrix(input)?;
    if size == 0 || rows % size != 0 || cols % size != 0 {
        return Err(ForziumError::Validation("invalid pool size".into()));
    }
    let out_rows = rows / size;
    let out_cols = cols / size;
    let mut out = vec![vec![0.0; out_cols]; out_rows];
    out.par_iter_mut().enumerate().for_each(|(r, out_row)| {
        let _guard = rayon_metrics::track_task();
        for c in 0..out_cols {
            let mut m = f64::NEG_INFINITY;
            for pr in 0..size {
                for pc in 0..size {
                    let val = input[r * size + pr][c * size + pc];
                    if val > m {
                        m = val;
                    }
                }
            }
            out_row[c] = m;
        }
    });
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn matmul_valid() {
        let a = vec![vec![1.0, 2.0], vec![3.0, 4.0]];
        let b = vec![vec![5.0, 6.0], vec![7.0, 8.0]];
        let res = matmul(&a, &b).unwrap();
        assert_eq!(res, vec![vec![19.0, 22.0], vec![43.0, 50.0]]);
    }

    #[test]
    fn simd_matmul_matches() {
        let a = vec![vec![1.0, 2.0], vec![3.0, 4.0]];
        let b = vec![vec![5.0, 6.0], vec![7.0, 8.0]];
        let res = simd_matmul(&a, &b).unwrap();
        assert_eq!(res, vec![vec![19.0, 22.0], vec![43.0, 50.0]]);
    }

    #[test]
    fn transpose_valid() {
        let m = vec![vec![1.0, 2.0, 3.0]];
        let res = transpose(&m).unwrap();
        assert_eq!(res, vec![vec![1.0], vec![2.0], vec![3.0]]);
    }

    #[test]
    fn matmul_shape_mismatch() {
        let a = vec![vec![1.0, 2.0]];
        let b = vec![vec![1.0], vec![2.0], vec![3.0]];
        let err = matmul(&a, &b).unwrap_err();
        matches!(err, ForziumError::Validation(_));
    }

    #[test]
    fn matmul_parallel_speedup() {
        use rayon::ThreadPoolBuilder;
        use std::time::Instant;

        let size = 150;
        let a = vec![vec![1.0; size]; size];
        let b = vec![vec![1.0; size]; size];

        let pool1 = ThreadPoolBuilder::new().num_threads(1).build().unwrap();
        let single = pool1.install(|| {
            let start = Instant::now();
            matmul(&a, &b).unwrap();
            start.elapsed()
        });

        let pool4 = ThreadPoolBuilder::new().num_threads(4).build().unwrap();
        let parallel = pool4.install(|| {
            let start = Instant::now();
            matmul(&a, &b).unwrap();
            start.elapsed()
        });

        assert!(parallel < single);
    }
}
