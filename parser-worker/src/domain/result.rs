use serde::{Deserialize, Serialize};

use crate::domain::order::Order;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ParseResult {
    pub request_id: String,
    pub fetched_at: i64,
    pub total_count: u32,
    pub next_cursor: Option<String>,
    pub orders: Vec<Order>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct BoardPage {
    pub orders: Vec<Order>,
    pub next_cursor: Option<String>,
    pub total_count: u32,
    pub server_ts: i64,
}
