use serde_json::{Value, json};

use crate::domain::BoardFilter;

pub(crate) const BOARD_QUERY: &str = include_str!("board_query.graphql");

pub(crate) fn build_body(filter: &BoardFilter, cursor: Option<&str>) -> Value {
    json!({ "query": BOARD_QUERY, "variables": build_variables(filter, cursor) })
}

fn build_variables(filter: &BoardFilter, cursor: Option<&str>) -> Value {
    let board_filter = if filter.raw_filter.is_null() {
        json!({})
    } else {
        filter.raw_filter.clone()
    };

    let mut variables = json!({
        "allVerticals": filter.all_verticals,
        "searchQuery": filter.search_query,
        "searchEntities": [],
        "pageSize": filter.page_size,
        "useSavedFilter": filter.use_saved_filter,
        "sort": filter.sort.as_api(),
        "filter": board_filter,
    });

    if let Some(cursor) = cursor {
        variables["nextCursor"] = json!(cursor);
    }

    variables
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_variables_match_profi_shape() {
        let body = build_body(&BoardFilter::default(), None);
        let vars = &body["variables"];

        assert_eq!(vars["allVerticals"], json!(true));
        assert_eq!(vars["pageSize"], json!(10));
        assert_eq!(vars["sort"], json!("DEFAULT"));
        assert_eq!(vars["searchEntities"], json!([]));
        assert_eq!(vars["filter"], json!({}));
        assert!(vars.get("nextCursor").is_none());
    }

    #[test]
    fn cursor_is_added_when_present() {
        let body = build_body(&BoardFilter::default(), Some("NEXT=="));
        assert_eq!(body["variables"]["nextCursor"], json!("NEXT=="));
    }

    #[test]
    fn body_carries_signed_query() {
        let body = build_body(&BoardFilter::default(), None);
        let query = body["query"].as_str().unwrap();
        assert!(query.starts_with("#prfrtkn:webbo:"));
    }
}
