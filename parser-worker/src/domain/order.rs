use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Order {
    pub id: String,
    pub title: String,
    pub description: String,
    pub price: Option<Price>,
    pub geo: Geo,
    pub client: Client,
    pub badges: Vec<Badge>,
    pub schedule: Option<String>,
    pub last_update: i64,
    pub score: f64,
    pub is_fresh: bool,
    pub is_viewed: bool,
    pub coordinates: Option<Coordinates>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Price {
    pub prefix: String,
    pub value: String,
    pub suffix: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Coordinates {
    pub lat: f64,
    pub lon: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Client {
    pub name: String,
    pub tags: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Badge {
    pub id: String,
    pub image_key: String,
    pub label: String,
}

#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
pub struct Geo {
    pub remote: Option<GeoPlace>,
    pub order_location: Option<GeoPlace>,
    pub client_may_come: Option<GeoPlace>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct GeoPlace {
    pub prefix: String,
    pub suffix: String,
    pub address: Option<String>,
}
