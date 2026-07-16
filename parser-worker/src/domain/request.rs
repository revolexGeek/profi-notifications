use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ParseRequest {
    pub request_id: String,
    #[serde(default)]
    pub filter: BoardFilter,
    #[serde(default)]
    pub max_pages: Option<u32>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct BoardFilter {
    #[serde(default)]
    pub search_query: String,
    #[serde(default = "default_page_size")]
    pub page_size: u32,
    #[serde(default)]
    pub sort: SortOrder,
    #[serde(default = "default_true")]
    pub all_verticals: bool,
    #[serde(default = "default_true")]
    pub use_saved_filter: bool,
    #[serde(default)]
    pub raw_filter: serde_json::Value,
}

impl Default for BoardFilter {
    fn default() -> Self {
        Self {
            search_query: String::new(),
            page_size: default_page_size(),
            sort: SortOrder::default(),
            all_verticals: true,
            use_saved_filter: true,
            raw_filter: serde_json::Value::Null,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize, Deserialize)]
pub enum SortOrder {
    #[default]
    #[serde(rename = "DEFAULT")]
    Default,
    #[serde(rename = "DATE")]
    Date,
}

impl SortOrder {
    pub fn as_api(self) -> &'static str {
        match self {
            SortOrder::Default => "DEFAULT",
            SortOrder::Date => "DATE",
        }
    }
}

fn default_page_size() -> u32 {
    10
}

fn default_true() -> bool {
    true
}
