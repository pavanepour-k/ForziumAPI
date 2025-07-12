#[pymodule]
fn _rust_lib(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(validate_buffer_py, m)?)?;
    m.add_function(wrap_pyfunction!(validate_utf8_py, m)?)?;
    m.add_function(wrap_pyfunction!(validate_u8_range_py, m)?)?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}
