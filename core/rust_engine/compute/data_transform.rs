//! Data preprocessing and transformation routines.

use crate::error::ForziumError;

fn validate_vec(v: &[f64]) -> Result<(), ForziumError> {
    if v.is_empty() {
        return Err(ForziumError::Validation("empty vector".into()));
    }
    Ok(())
}

/// Scale all elements of the vector by `factor`.
pub fn scale(v: &[f64], factor: f64) -> Result<Vec<f64>, ForziumError> {
    validate_vec(v)?;
    Ok(v.iter().map(|x| x * factor).collect())
}

/// Normalize elements into the 0..1 range using min-max scaling.
pub fn normalize(v: &[f64]) -> Result<Vec<f64>, ForziumError> {
    validate_vec(v)?;
    let (min, max) = v
        .iter()
        .fold((f64::INFINITY, f64::NEG_INFINITY), |(mn, mx), &x| {
            (mn.min(x), mx.max(x))
        });
    if min == max {
        return Err(ForziumError::Validation("constant vector".into()));
    }
    Ok(v.iter().map(|x| (x - min) / (max - min)).collect())
}

/// Reshape `v` into a matrix with `rows` × `cols` dimensions.
pub fn reshape(v: &[f64], rows: usize, cols: usize) -> Result<Vec<Vec<f64>>, ForziumError> {
    validate_vec(v)?;
    if rows == 0 || cols == 0 {
        return Err(ForziumError::Validation("zero dimension".into()));
    }
    if rows * cols != v.len() {
        return Err(ForziumError::Validation("shape mismatch".into()));
    }
    let mut out = vec![vec![0.0; cols]; rows];
    for i in 0..rows {
        for j in 0..cols {
            out[i][j] = v[i * cols + j];
        }
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn scale_valid() {
        let v = vec![1.0, 2.0];
        assert_eq!(scale(&v, 2.0).unwrap(), vec![2.0, 4.0]);
    }

    #[test]
    fn normalize_valid() {
        let v = vec![1.0, 3.0, 5.0];
        assert_eq!(normalize(&v).unwrap(), vec![0.0, 0.5, 1.0]);
    }

    #[test]
    fn reshape_valid() {
        let v = vec![1.0, 2.0, 3.0, 4.0];
        assert_eq!(
            reshape(&v, 2, 2).unwrap(),
            vec![vec![1.0, 2.0], vec![3.0, 4.0]],
        );
    }

    #[test]
    fn normalize_constant_error() {
        let v = vec![2.0, 2.0];
        matches!(normalize(&v).unwrap_err(), ForziumError::Validation(_));
    }

    #[test]
    fn reshape_shape_error() {
        let v = vec![1.0, 2.0, 3.0];
        matches!(reshape(&v, 2, 2).unwrap_err(), ForziumError::Validation(_));
    }
}
