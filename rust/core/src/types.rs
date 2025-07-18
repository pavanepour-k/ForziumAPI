//! # FORZIUM TYPE DEFINITIONS
//!
//! **CRITICAL**: Core data structures for input/output processing
//! **MANDATE**: ALL public APIs MUST use these standardized types

#![allow(dead_code)] // Allow during development phase

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// **INPUT DATA CONTAINER**
///
/// **PURPOSE**: Standardized input data representation
/// **GUARANTEE**: Serializable, validated input processing
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InputData {
    /// **FIELD IDENTIFIER**
    pub field: String,
    
    /// **RAW DATA PAYLOAD**
    pub data: Vec<u8>,
    
    /// **CONTENT TYPE**
    pub content_type: Option<String>,
    
    /// **VALIDATION METADATA**
    pub metadata: HashMap<String, serde_json::Value>,
}

/// **OUTPUT DATA CONTAINER**
///
/// **PURPOSE**: Standardized output data representation  
/// **GUARANTEE**: Consistent response formatting
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OutputData {
    /// **RESULT PAYLOAD**
    pub result: String,
    
    /// **STATUS CODE**
    pub status: u16,

    /// **RESPONSE HEADERS**
    pub headers: HashMap<String, String>,
    
    /// **PROCESSING METADATA**
    pub metadata: HashMap<String, serde_json::Value>,
}

impl InputData {
    /// **CONSTRUCTOR**
    pub fn new(field: impl Into<String>, data: Vec<u8>) -> Self {
        Self {
            field: field.into(),
            data,
            content_type: None,
            metadata: HashMap::new(),
        }
    }
    
    /// **WITH CONTENT TYPE**
    pub fn with_content_type(mut self, content_type: impl Into<String>) -> Self {
        self.content_type = Some(content_type.into());
        self
    }
}

impl OutputData {
    /// **CONSTRUCTOR**
    pub fn new(result: impl Into<String>, status: u16) -> Self {
        Self {
            result: result.into(),
            status,
            headers: std::collections::HashMap::new(),
            metadata: std::collections::HashMap::new(),
        }
    }
    
    /// **SUCCESS CONSTRUCTOR**
    pub fn success(result: impl Into<String>) -> Self {
        Self::new(result, 200)
    }
    
    /// **ERROR CONSTRUCTOR**
    pub fn error(message: impl Into<String>, status: u16) -> Self {
        Self::new(message, status)
    }
}
