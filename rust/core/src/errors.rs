use thiserror::Error;

#[derive(Debug, Error)]
pub enum ProjectError {
    #[error("VALIDATION ERROR: {code} - {message}")]
    Validation { code: String, message: String },
    
    #[error("PROCESSING ERROR: {code} - {message}")]
    Processing { code: String, message: String },

    #[error("TIMEOUT ERROR: operation exceeded {timeout}s")]
    Timeout { timeout: u64 },
    
    #[error("SYSTEM ERROR: {code} - {message}")]
    System { code: String, message: String },
}
