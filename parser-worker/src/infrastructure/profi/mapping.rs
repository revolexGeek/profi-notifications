use super::dto::{BadgeDto, BoardItems, GeoDto, GeoPlaceDto, Item, PriceDto};
use crate::domain::{Badge, BoardPage, Client, Coordinates, Geo, GeoPlace, Order, Price};

const SNIPPET: &str = "SNIPPET";

pub(crate) fn to_board_page(board: BoardItems) -> BoardPage {
    let orders = board.items.into_iter().filter_map(to_order).collect();

    BoardPage {
        orders,
        next_cursor: board.next_cursor,
        total_count: board.total_count,
        server_ts: board.server_ts,
    }
}

fn to_order(item: Item) -> Option<Order> {
    if item.item_type.as_deref() != Some(SNIPPET) {
        return None;
    }
    let id = item.id?;

    Some(Order {
        id,
        title: item.title.unwrap_or_default(),
        description: item.description.unwrap_or_default(),
        price: item.price.and_then(to_price),
        geo: item.geo.map(to_geo).unwrap_or_default(),
        client: Client {
            name: item
                .client_info
                .and_then(|info| info.name)
                .unwrap_or_default(),
            tags: item
                .client_tags
                .into_iter()
                .filter_map(|tag| tag.value)
                .collect(),
        },
        badges: item.badges.into_iter().filter_map(to_badge).collect(),
        schedule: item.schedule.filter(|value| !value.is_empty()),
        last_update: item.last_update_date.unwrap_or_default(),
        score: item.score.unwrap_or_default(),
        is_fresh: item.is_fresh.unwrap_or_default(),
        is_viewed: item.is_viewed.unwrap_or_default(),
        coordinates: item.coordinates.map(|c| Coordinates {
            lat: c.lat,
            lon: c.lon,
        }),
    })
}

fn to_price(price: PriceDto) -> Option<Price> {
    let value = price.value?;
    Some(Price {
        prefix: price.prefix.unwrap_or_default(),
        value,
        suffix: price.suffix.unwrap_or_default(),
    })
}

fn to_geo(geo: GeoDto) -> Geo {
    Geo {
        remote: geo.remote.and_then(to_geo_place),
        order_location: geo.order_location.and_then(to_geo_place),
        client_may_come: geo.client_may_come.and_then(to_geo_place),
    }
}

fn to_geo_place(place: GeoPlaceDto) -> Option<GeoPlace> {
    let prefix = place.prefix.filter(|value| !value.is_empty())?;
    Some(GeoPlace {
        prefix,
        suffix: place.suffix.unwrap_or_default(),
        address: place.address,
    })
}

fn to_badge(badge: BadgeDto) -> Option<Badge> {
    let id = badge.id?;
    Some(Badge {
        id,
        image_key: badge.image_key.unwrap_or_default(),
        label: badge.label.unwrap_or_default(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    const FIXTURE: &str = r#"{"data":{"boSearchBoardItems":{
      "nextCursor":"CURSOR==","serverTs":1784135987,"totalCount":28,
      "analytics":{"boardSearchQuery":null,"boardSearchUsed":false},
      "items":[
        {"id":"1","type":"SNIPPET","score":80.5,"title":"Девопс услуги","description":"настроить tailscale","isReposted":false,"lastUpdateDate":1784133513,"noticeLabel":null,
         "price":{"prefix":"до","suffix":"","value":"700 ₽"},
         "geo":{"clientMayCome":{"address":null,"geoplaces":null,"prefix":null,"suffix":null},"orderLocation":{"address":null,"geoplaces":null,"prefix":null,"suffix":null},"remote":{"address":null,"geoplaces":null,"prefix":"Дистанционно · Москва","suffix":""}},
         "clientInfo":{"name":"Георгий"},"clientTags":[],"badges":[],"status":null,"schedule":"15 июл.","isFresh":false,"isStandard":true,"isViewed":false,"coordinates":null},
        {"id":"2","type":"SNIPPET","score":80.4,"title":"ИИ агент","description":"настройка","isReposted":false,"lastUpdateDate":1784133352,
         "price":{"prefix":"до","suffix":"","value":"20 000 ₽"},
         "geo":{"clientMayCome":null,"orderLocation":null,"remote":{"prefix":"Дистанционно","suffix":"","address":null}},
         "clientInfo":{"name":"Анастасия"},"clientTags":[{"value":"новый"}],
         "badges":[{"id":"newbieDiscount","imageKey":"PERCENT","label":"Скидка"}],
         "schedule":"","isFresh":true,"isViewed":false,"coordinates":{"lat":55.75,"lon":37.61}},
        {"id":"d1","type":"DIVIDER","title":"Разделитель"}
      ]}}}"#;

    fn page() -> BoardPage {
        use super::super::dto::GraphqlResponse;
        let response: GraphqlResponse = serde_json::from_str(FIXTURE).expect("valid fixture");
        to_board_page(response.data.expect("data present").board)
    }

    #[test]
    fn keeps_only_snippets() {
        assert_eq!(page().orders.len(), 2);
    }

    #[test]
    fn carries_pagination_metadata() {
        let page = page();
        assert_eq!(page.total_count, 28);
        assert_eq!(page.next_cursor.as_deref(), Some("CURSOR=="));
        assert_eq!(page.server_ts, 1784135987);
    }

    #[test]
    fn maps_core_snippet_fields() {
        let order = &page().orders[0];
        assert_eq!(order.id, "1");
        assert_eq!(order.title, "Девопс услуги");
        assert_eq!(order.client.name, "Георгий");
        assert_eq!(order.price.as_ref().unwrap().value, "700 ₽");
        assert_eq!(
            order.geo.remote.as_ref().unwrap().prefix,
            "Дистанционно · Москва"
        );
        assert_eq!(order.schedule.as_deref(), Some("15 июл."));
        assert!(order.coordinates.is_none());
    }

    #[test]
    fn drops_empty_geo_places() {
        let order = &page().orders[0];
        assert!(order.geo.order_location.is_none());
        assert!(order.geo.client_may_come.is_none());
    }

    #[test]
    fn maps_tags_badges_coordinates_and_empty_schedule() {
        let order = &page().orders[1];
        assert_eq!(order.client.tags, vec!["новый".to_string()]);
        assert_eq!(order.badges[0].id, "newbieDiscount");
        assert_eq!(order.badges[0].label, "Скидка");
        assert!(order.is_fresh);
        assert_eq!(order.coordinates.as_ref().unwrap().lat, 55.75);
        assert!(order.schedule.is_none());
    }
}
