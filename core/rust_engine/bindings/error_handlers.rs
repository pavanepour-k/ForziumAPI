use pyo3::prelude::*;

use crate::error::ForziumError;

/// Map a [`ForziumError`] into a Python exception.
pub fn map_error(err: ForziumError) -> PyErr {
    err.into()
}
