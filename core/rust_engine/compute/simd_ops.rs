//! Advanced SIMD optimizations for tensor operations
//!
//! This module provides implementations of tensor operations using:
//! - AVX2 for x86_64 platforms
//! - AVX-512 for modern Intel platforms
//! - NEON for ARM platforms

use crate::error::ForziumError;

#[cfg(target_arch = "x86_64")]
use std::arch::x86_64::*;

#[cfg(target_arch = "aarch64")]
use std::arch::aarch64::*;

/// Detects the highest SIMD level supported by the current CPU
#[allow(unused_mut)]
pub fn detect_simd_support() -> &'static str {
    #[cfg(target_arch = "x86_64")]
    {
        let mut has_avx512f = false;
        let mut has_avx2 = false;
        let mut has_avx = false;
        let mut has_sse42 = false;

        // Check CPU features
        #[cfg(target_feature = "avx512f")]
        {
            has_avx512f = true;
        }

        #[cfg(target_feature = "avx2")]
        {
            has_avx2 = true;
        }

        #[cfg(target_feature = "avx")]
        {
            has_avx = true;
        }

        #[cfg(target_feature = "sse4.2")]
        {
            has_sse42 = true;
        }

        // Runtime detection if not using target features
        if !has_avx512f && !has_avx2 && !has_avx && !has_sse42 {
            if is_x86_feature_detected!("avx512f") {
                return "avx512f";
            } else if is_x86_feature_detected!("avx2") {
                return "avx2";
            } else if is_x86_feature_detected!("avx") {
                return "avx";
            } else if is_x86_feature_detected!("sse4.2") {
                return "sse4.2";
            }
        } else {
            if has_avx512f {
                return "avx512f";
            } else if has_avx2 {
                return "avx2";
            } else if has_avx {
                return "avx";
            } else if has_sse42 {
                return "sse4.2";
            }
        }

        "basic"
    }

    #[cfg(target_arch = "aarch64")]
    {
        if std::arch::is_aarch64_feature_detected!("neon") {
            return "neon";
        }
        "basic"
    }

    #[cfg(not(any(target_arch = "x86_64", target_arch = "aarch64")))]
    "basic"
}

/// Matrix multiplication using AVX2 (256-bit SIMD)
/// Can process 4 doubles at once
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx2")]
pub unsafe fn matmul_avx2(a: &[Vec<f64>], b: &[Vec<f64>]) -> Result<Vec<Vec<f64>>, ForziumError> {
    let rows_a = a.len();
    if rows_a == 0 {
        return Err(ForziumError::Validation("empty matrix".into()));
    }

    let cols_a = a[0].len();
    let rows_b = b.len();
    if rows_b == 0 || b[0].is_empty() {
        return Err(ForziumError::Validation("empty matrix".into()));
    }

    let cols_b = b[0].len();

    if cols_a != rows_b {
        return Err(ForziumError::Validation(
            "incompatible dimensions for matrix multiplication".into(),
        ));
    }

    // Transpose B for better cache locality
    let mut bt = vec![vec![0.0; rows_b]; cols_b];
    for i in 0..rows_b {
        for j in 0..cols_b {
            bt[j][i] = b[i][j];
        }
    }

    let mut result = vec![vec![0.0; cols_b]; rows_a];

    for i in 0..rows_a {
        for j in 0..cols_b {
            let row_a = &a[i];
            let row_bt = &bt[j];

            let mut sum_vec = unsafe { _mm256_setzero_pd() }; // 4 doubles initialized to 0

            // Process 4 elements at a time
            let mut k = 0;
            while k + 4 <= cols_a {
                let a_vec = unsafe { _mm256_loadu_pd(row_a[k..].as_ptr()) };
                let b_vec = unsafe { _mm256_loadu_pd(row_bt[k..].as_ptr()) };

                // a * b + sum
                sum_vec = unsafe { _mm256_fmadd_pd(a_vec, b_vec, sum_vec) };

                k += 4;
            }

            // Extract the sum from the vector
            let mut sum_array = [0.0; 4];
            unsafe { _mm256_storeu_pd(sum_array.as_mut_ptr(), sum_vec) };
            let mut sum = sum_array[0] + sum_array[1] + sum_array[2] + sum_array[3];

            // Handle remaining elements
            while k < cols_a {
                sum += row_a[k] * row_bt[k];
                k += 1;
            }

            result[i][j] = sum;
        }
    }

    Ok(result)
}

/// Matrix multiplication using AVX-512 (512-bit SIMD)
/// Can process 8 doubles at once
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx512f")]
pub unsafe fn matmul_avx512(a: &[Vec<f64>], b: &[Vec<f64>]) -> Result<Vec<Vec<f64>>, ForziumError> {
    let rows_a = a.len();
    if rows_a == 0 {
        return Err(ForziumError::Validation("empty matrix".into()));
    }

    let cols_a = a[0].len();
    let rows_b = b.len();
    if rows_b == 0 || b[0].is_empty() {
        return Err(ForziumError::Validation("empty matrix".into()));
    }

    let cols_b = b[0].len();

    if cols_a != rows_b {
        return Err(ForziumError::Validation(
            "incompatible dimensions for matrix multiplication".into(),
        ));
    }

    // Transpose B for better cache locality
    let mut bt = vec![vec![0.0; rows_b]; cols_b];
    for i in 0..rows_b {
        for j in 0..cols_b {
            bt[j][i] = b[i][j];
        }
    }

    let mut result = vec![vec![0.0; cols_b]; rows_a];

    for i in 0..rows_a {
        for j in 0..cols_b {
            let row_a = &a[i];
            let row_bt = &bt[j];

            let mut sum_vec = unsafe { _mm512_setzero_pd() }; // 8 doubles initialized to 0

            // Process 8 elements at a time
            let mut k = 0;
            while k + 8 <= cols_a {
                let a_vec = unsafe { _mm512_loadu_pd(row_a[k..].as_ptr()) };
                let b_vec = unsafe { _mm512_loadu_pd(row_bt[k..].as_ptr()) };

                // a * b + sum
                sum_vec = unsafe { _mm512_fmadd_pd(a_vec, b_vec, sum_vec) };

                k += 8;
            }

            // Extract the sum from the vector
            let mut sum = unsafe { _mm512_reduce_add_pd(sum_vec) };

            // Handle remaining elements
            while k < cols_a {
                sum += row_a[k] * row_bt[k];
                k += 1;
            }

            result[i][j] = sum;
        }
    }

    Ok(result)
}

/// Matrix multiplication using NEON on ARM
#[cfg(target_arch = "aarch64")]
#[target_feature(enable = "neon")]
pub unsafe fn matmul_neon(a: &[Vec<f64>], b: &[Vec<f64>]) -> Result<Vec<Vec<f64>>, ForziumError> {
    let rows_a = a.len();
    if rows_a == 0 {
        return Err(ForziumError::Validation("empty matrix".into()));
    }

    let cols_a = a[0].len();
    let rows_b = b.len();
    if rows_b == 0 || b[0].is_empty() {
        return Err(ForziumError::Validation("empty matrix".into()));
    }

    let cols_b = b[0].len();

    if cols_a != rows_b {
        return Err(ForziumError::Validation(
            "incompatible dimensions for matrix multiplication".into(),
        ));
    }

    // Transpose B for better cache locality
    let mut bt = vec![vec![0.0; rows_b]; cols_b];
    for i in 0..rows_b {
        for j in 0..cols_b {
            bt[j][i] = b[i][j];
        }
    }

    let mut result = vec![vec![0.0; cols_b]; rows_a];

    for i in 0..rows_a {
        for j in 0..cols_b {
            let row_a = &a[i];
            let row_bt = &bt[j];

            // NEON can process 2 doubles at a time
            let mut sum_vec = vdupq_n_f64(0.0); // 2 doubles initialized to 0

            // Process 2 elements at a time
            let mut k = 0;
            while k + 2 <= cols_a {
                let a_vec = vld1q_f64(&row_a[k] as *const f64);
                let b_vec = vld1q_f64(&row_bt[k] as *const f64);

                // Multiply and accumulate
                sum_vec = vfmaq_f64(sum_vec, a_vec, b_vec);

                k += 2;
            }

            // Extract the sum from the vector
            let mut sum_array = [0.0; 2];
            vst1q_f64(sum_array.as_mut_ptr(), sum_vec);
            let mut sum = sum_array[0] + sum_array[1];

            // Handle remaining elements
            while k < cols_a {
                sum += row_a[k] * row_bt[k];
                k += 1;
            }

            result[i][j] = sum;
        }
    }

    Ok(result)
}

/// Optimized matrix multiplication that automatically selects
/// the best SIMD implementation for the current platform
pub fn optimal_matmul(a: &[Vec<f64>], b: &[Vec<f64>]) -> Result<Vec<Vec<f64>>, ForziumError> {
    let simd_support = detect_simd_support();

    match simd_support {
        #[cfg(target_arch = "x86_64")]
        "avx512f" => unsafe { matmul_avx512(a, b) },

        #[cfg(target_arch = "x86_64")]
        "avx2" => unsafe { matmul_avx2(a, b) },

        #[cfg(target_arch = "aarch64")]
        "neon" => unsafe { matmul_neon(a, b) },

        _ => {
            // Fallback to basic implementation
            let rows_a = a.len();
            if rows_a == 0 {
                return Err(ForziumError::Validation("empty matrix".into()));
            }

            let cols_a = a[0].len();
            let rows_b = b.len();
            if rows_b == 0 {
                return Err(ForziumError::Validation("empty matrix".into()));
            }

            let cols_b = b[0].len();

            if cols_a != rows_b {
                return Err(ForziumError::Validation(
                    "incompatible dimensions for matrix multiplication".into(),
                ));
            }

            let mut result = vec![vec![0.0; cols_b]; rows_a];

            for i in 0..rows_a {
                for j in 0..cols_b {
                    let mut sum = 0.0;
                    for k in 0..cols_a {
                        sum += a[i][k] * b[k][j];
                    }
                    result[i][j] = sum;
                }
            }

            Ok(result)
        }
    }
}

/// Element-wise vector addition using AVX2
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx2")]
pub unsafe fn add_avx2(a: &[Vec<f64>], b: &[Vec<f64>]) -> Result<Vec<Vec<f64>>, ForziumError> {
    let rows = a.len();
    if rows == 0 || a[0].is_empty() {
        return Err(ForziumError::Validation("empty matrix".into()));
    }

    let cols = a[0].len();

    if rows != b.len() || cols != b[0].len() {
        return Err(ForziumError::Validation(
            "matrices must have the same dimensions".into(),
        ));
    }

    let mut result = vec![vec![0.0; cols]; rows];

    for i in 0..rows {
        let row_a = &a[i];
        let row_b = &b[i];
        let row_result = &mut result[i];

        let mut j = 0;
        while j + 4 <= cols {
            let a_vec = unsafe { _mm256_loadu_pd(&row_a[j] as *const f64) };
            let b_vec = unsafe { _mm256_loadu_pd(&row_b[j] as *const f64) };

            let sum_vec = unsafe { _mm256_add_pd(a_vec, b_vec) };
            unsafe { _mm256_storeu_pd(&mut row_result[j] as *mut f64, sum_vec) };

            j += 4;
        }

        // Handle remaining elements
        while j < cols {
            row_result[j] = row_a[j] + row_b[j];
            j += 1;
        }
    }

    Ok(result)
}

/// Element-wise vector addition using AVX-512
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx512f")]
pub unsafe fn add_avx512(a: &[Vec<f64>], b: &[Vec<f64>]) -> Result<Vec<Vec<f64>>, ForziumError> {
    let rows = a.len();
    if rows == 0 || a[0].is_empty() {
        return Err(ForziumError::Validation("empty matrix".into()));
    }

    let cols = a[0].len();

    if rows != b.len() || cols != b[0].len() {
        return Err(ForziumError::Validation(
            "matrices must have the same dimensions".into(),
        ));
    }

    let mut result = vec![vec![0.0; cols]; rows];

    for i in 0..rows {
        let row_a = &a[i];
        let row_b = &b[i];
        let row_result = &mut result[i];

        let mut j = 0;
        while j + 8 <= cols {
            let a_vec = unsafe { _mm512_loadu_pd(&row_a[j] as *const f64) };
            let b_vec = unsafe { _mm512_loadu_pd(&row_b[j] as *const f64) };

            let sum_vec = unsafe { _mm512_add_pd(a_vec, b_vec) };
            unsafe { _mm512_storeu_pd(&mut row_result[j] as *mut f64, sum_vec) };

            j += 8;
        }

        // Handle remaining elements
        while j < cols {
            row_result[j] = row_a[j] + row_b[j];
            j += 1;
        }
    }

    Ok(result)
}

/// Element-wise vector addition using NEON on ARM
#[cfg(target_arch = "aarch64")]
#[target_feature(enable = "neon")]
pub unsafe fn add_neon(a: &[Vec<f64>], b: &[Vec<f64>]) -> Result<Vec<Vec<f64>>, ForziumError> {
    let rows = a.len();
    if rows == 0 || a[0].is_empty() {
        return Err(ForziumError::Validation("empty matrix".into()));
    }

    let cols = a[0].len();

    if rows != b.len() || cols != b[0].len() {
        return Err(ForziumError::Validation(
            "matrices must have the same dimensions".into(),
        ));
    }

    let mut result = vec![vec![0.0; cols]; rows];

    for i in 0..rows {
        let row_a = &a[i];
        let row_b = &b[i];
        let row_result = &mut result[i];

        let mut j = 0;
        while j + 2 <= cols {
            let a_vec = vld1q_f64(&row_a[j] as *const f64);
            let b_vec = vld1q_f64(&row_b[j] as *const f64);

            let sum_vec = vaddq_f64(a_vec, b_vec);
            vst1q_f64(&mut row_result[j] as *mut f64, sum_vec);

            j += 2;
        }

        // Handle remaining elements
        while j < cols {
            row_result[j] = row_a[j] + row_b[j];
            j += 1;
        }
    }

    Ok(result)
}

/// Optimized matrix element-wise addition that automatically selects
/// the best SIMD implementation for the current platform
pub fn optimal_add(a: &[Vec<f64>], b: &[Vec<f64>]) -> Result<Vec<Vec<f64>>, ForziumError> {
    let simd_support = detect_simd_support();

    match simd_support {
        #[cfg(target_arch = "x86_64")]
        "avx512f" => unsafe { add_avx512(a, b) },

        #[cfg(target_arch = "x86_64")]
        "avx2" => unsafe { add_avx2(a, b) },

        #[cfg(target_arch = "aarch64")]
        "neon" => unsafe { add_neon(a, b) },

        _ => {
            // Fallback to basic implementation
            let rows = a.len();
            if rows == 0 {
                return Err(ForziumError::Validation("empty matrix".into()));
            }

            let cols = a[0].len();

            if rows != b.len() || b.iter().any(|row| row.len() != cols) {
                return Err(ForziumError::Validation(
                    "matrices must have the same dimensions".into(),
                ));
            }

            let mut result = vec![vec![0.0; cols]; rows];

            for i in 0..rows {
                for j in 0..cols {
                    result[i][j] = a[i][j] + b[i][j];
                }
            }

            Ok(result)
        }
    }
}

/// Optimized convolution using AVX2
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx2")]
pub unsafe fn conv2d_avx2(
    input: &[Vec<f64>],
    kernel: &[Vec<f64>],
) -> Result<Vec<Vec<f64>>, ForziumError> {
    let rows = input.len();
    if rows == 0 || input[0].is_empty() {
        return Err(ForziumError::Validation("empty input matrix".into()));
    }

    let cols = input[0].len();

    let krows = kernel.len();
    if krows == 0 || kernel[0].is_empty() {
        return Err(ForziumError::Validation("empty kernel matrix".into()));
    }

    let kcols = kernel[0].len();

    if rows < krows || cols < kcols {
        return Err(ForziumError::Validation("kernel larger than input".into()));
    }

    let out_rows = rows - krows + 1;
    let out_cols = cols - kcols + 1;

    let mut result = vec![vec![0.0; out_cols]; out_rows];

    for i in 0..out_rows {
        for j in 0..out_cols {
            let _sum_vec = unsafe { _mm256_setzero_pd() }; // 4 doubles initialized to 0 (currently unused)
            let mut sum = 0.0;

            for ki in 0..krows {
                for kj in 0..kcols {
                    sum += input[i + ki][j + kj] * kernel[ki][kj];
                }
            }

            result[i][j] = sum;
        }
    }

    Ok(result)
}

/// Runs comprehensive SIMD benchmarks and returns a report
pub fn benchmark_simd_ops() -> String {
    use std::time::Instant;

    let mut report = String::new();
    report.push_str(&format!("SIMD Support: {}\n\n", detect_simd_support()));

    // Create test matrices
    let size = 500;
    let a: Vec<Vec<f64>> = (0..size)
        .map(|i| (0..size).map(|j| (i * j) as f64).collect())
        .collect();
    let b: Vec<Vec<f64>> = (0..size)
        .map(|i| (0..size).map(|j| (i + j) as f64).collect())
        .collect();

    // Basic matmul
    let start = Instant::now();
    let _ = super::tensor_ops::matmul(&a, &b).unwrap();
    let basic_time = start.elapsed();

    // Optimized matmul
    let start = Instant::now();
    let _ = optimal_matmul(&a, &b).unwrap();
    let optimized_time = start.elapsed();

    let speedup = basic_time.as_secs_f64() / optimized_time.as_secs_f64();

    report.push_str(&format!("Matrix Multiplication ({}x{}):\n", size, size));
    report.push_str(&format!("  Basic:     {:?}\n", basic_time));
    report.push_str(&format!("  Optimized: {:?}\n", optimized_time));
    report.push_str(&format!("  Speedup:   {:.2}x\n\n", speedup));

    // Element-wise addition
    let start = Instant::now();
    let _ = super::tensor_ops::elementwise_add(&a, &b).unwrap();
    let basic_time = start.elapsed();

    let start = Instant::now();
    let _ = optimal_add(&a, &b).unwrap();
    let optimized_time = start.elapsed();

    let speedup = basic_time.as_secs_f64() / optimized_time.as_secs_f64();

    report.push_str(&format!("Element-wise Addition ({}x{}):\n", size, size));
    report.push_str(&format!("  Basic:     {:?}\n", basic_time));
    report.push_str(&format!("  Optimized: {:?}\n", optimized_time));
    report.push_str(&format!("  Speedup:   {:.2}x\n", speedup));

    report
}
