use forzium_engine::compute::{rayon_metrics, tensor_ops};
use std::error::Error;

fn main() -> Result<(), Box<dyn Error>> {
    rayon_metrics::reset_metrics().map_err(|err| Box::<dyn Error>::from(err))?;

    let matrix_size = 128usize;
    let matrix_a = build_matrix(matrix_size, matrix_size, |r, c| (r + c) as f64);
    let matrix_b = build_matrix(matrix_size, matrix_size, |r, c| (r * 2 + c) as f64);

    for _ in 0..4 {
        tensor_ops::matmul(&matrix_a, &matrix_b).map_err(|err| Box::<dyn Error>::from(err))?;
    }

    tensor_ops::elementwise_add(&matrix_a, &matrix_b).map_err(|err| Box::<dyn Error>::from(err))?;
    tensor_ops::hadamard(&matrix_a, &matrix_b).map_err(|err| Box::<dyn Error>::from(err))?;

    let conv_input = build_matrix(96, 96, |r, c| ((r * c + r) % 97) as f64);
    let conv_kernel = build_matrix(5, 5, |r, c| (r + c + 1) as f64);
    tensor_ops::conv2d(&conv_input, &conv_kernel).map_err(|err| Box::<dyn Error>::from(err))?;

    let pool_input = build_matrix(128, 128, |r, c| ((r + c * 3) % 23) as f64);
    tensor_ops::max_pool2d(&pool_input, 4).map_err(|err| Box::<dyn Error>::from(err))?;

    let snapshot =
        rayon_metrics::snapshot_and_reset().map_err(|err| Box::<dyn Error>::from(err))?;
    let json = serde_json::to_string_pretty(&snapshot)?;
    println!("{}", json);
    Ok(())
}

fn build_matrix<F>(rows: usize, cols: usize, mut f: F) -> Vec<Vec<f64>>
where
    F: FnMut(usize, usize) -> f64,
{
    (0..rows)
        .map(|r| (0..cols).map(|c| f(r, c)).collect())
        .collect()
}
