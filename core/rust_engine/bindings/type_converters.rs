use pyo3::prelude::*;

/// Convert a Python sequence into a vector of integers.
pub fn py_list_to_vec_i64(seq: &Bound<PyAny>) -> PyResult<Vec<i64>> {
    seq.extract::<Vec<i64>>()
}
