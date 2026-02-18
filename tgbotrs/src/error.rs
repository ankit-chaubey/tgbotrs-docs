use thiserror::Error;

/// The main error type for tgbotrs.
#[derive(Debug, Error)]
pub enum BotError {
    /// HTTP request error from reqwest.
    #[error("HTTP error: {0}")]
    Http(#[from] reqwest::Error),

    /// JSON (de)serialization error.
    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),

    /// Telegram API returned ok=false.
    #[error("Telegram API error [{code}]: {description}")]
    Api {
        code: i64,
        description: String,
        /// Optional retry_after for flood-wait errors.
        retry_after: Option<i64>,
        /// Optional migrate_to_chat_id for migration errors.
        migrate_to_chat_id: Option<i64>,
    },

    /// Invalid bot token format.
    #[error("Invalid bot token")]
    InvalidToken,

    /// Other errors.
    #[error("{0}")]
    Other(String),
}

impl BotError {
    /// Returns true if this is a Telegram API error with a specific code.
    pub fn is_api_error_code(&self, expected_code: i64) -> bool {
        matches!(self, BotError::Api { code, .. } if *code == expected_code)
    }

    /// Returns true if the error is a flood-wait and returns the seconds to wait.
    pub fn flood_wait_seconds(&self) -> Option<i64> {
        if let BotError::Api { retry_after, .. } = self {
            return *retry_after;
        }
        None
    }
}
