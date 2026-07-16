use serde::Deserialize;

#[derive(Debug, Deserialize)]
pub struct GraphqlResponse {
    pub data: Option<ResponseData>,
    #[serde(default)]
    pub errors: Vec<GraphqlError>,
}

#[derive(Debug, Deserialize)]
pub struct GraphqlError {
    pub message: String,
}

#[derive(Debug, Deserialize)]
pub struct ResponseData {
    #[serde(rename = "boSearchBoardItems")]
    pub board: BoardItems,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BoardItems {
    pub next_cursor: Option<String>,
    #[serde(default)]
    pub server_ts: i64,
    #[serde(default)]
    pub total_count: u32,
    #[serde(default)]
    pub items: Vec<Item>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Item {
    #[serde(rename = "type")]
    pub item_type: Option<String>,
    pub id: Option<String>,
    pub title: Option<String>,
    pub description: Option<String>,
    pub score: Option<f64>,
    pub last_update_date: Option<i64>,
    pub is_fresh: Option<bool>,
    pub is_viewed: Option<bool>,
    pub schedule: Option<String>,
    pub price: Option<PriceDto>,
    pub geo: Option<GeoDto>,
    pub client_info: Option<ClientInfoDto>,
    #[serde(default)]
    pub client_tags: Vec<ClientTagDto>,
    #[serde(default)]
    pub badges: Vec<BadgeDto>,
    pub coordinates: Option<CoordinatesDto>,
}

#[derive(Debug, Deserialize)]
pub struct PriceDto {
    pub prefix: Option<String>,
    pub suffix: Option<String>,
    pub value: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GeoDto {
    pub remote: Option<GeoPlaceDto>,
    pub order_location: Option<GeoPlaceDto>,
    pub client_may_come: Option<GeoPlaceDto>,
}

#[derive(Debug, Deserialize)]
pub struct GeoPlaceDto {
    pub prefix: Option<String>,
    pub suffix: Option<String>,
    pub address: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct ClientInfoDto {
    pub name: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct ClientTagDto {
    pub value: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BadgeDto {
    pub id: Option<String>,
    pub image_key: Option<String>,
    pub label: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct CoordinatesDto {
    pub lat: f64,
    pub lon: f64,
}
