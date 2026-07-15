use crate::domain::{ParseRequest, ParseResult, ParserError, Result};

pub(crate) fn encode_result(result: &ParseResult) -> Result<Vec<u8>> {
    serde_json::to_vec(result).map_err(|error| ParserError::Publish(error.to_string()))
}

pub(crate) fn decode_request(bytes: &[u8]) -> Result<ParseRequest> {
    serde_json::from_slice(bytes).map_err(|error| ParserError::InvalidRequest(error.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::domain::BoardFilter;

    #[test]
    fn decodes_minimal_request() {
        let request = decode_request(br#"{"request_id":"r1"}"#).expect("valid");
        assert_eq!(request.request_id, "r1");
        assert_eq!(request.filter.page_size, 10);
        assert!(request.max_pages.is_none());
    }

    #[test]
    fn decodes_request_with_filter() {
        let raw =
            br#"{"request_id":"r2","filter":{"search_query":"go","page_size":25},"max_pages":3}"#;
        let request = decode_request(raw).expect("valid");
        assert_eq!(request.filter.search_query, "go");
        assert_eq!(request.filter.page_size, 25);
        assert_eq!(request.max_pages, Some(3));
    }

    #[test]
    fn rejects_malformed_request() {
        let error = decode_request(b"}{").unwrap_err();
        assert!(matches!(error, ParserError::InvalidRequest(_)));
    }

    #[test]
    fn encodes_result_roundtrips() {
        let result = ParseResult {
            request_id: "r1".to_string(),
            fetched_at: 1_700_000_000,
            total_count: 5,
            next_cursor: Some("c==".to_string()),
            orders: vec![],
        };

        let bytes = encode_result(&result).expect("encoded");
        let decoded: ParseResult = serde_json::from_slice(&bytes).expect("valid json");
        assert_eq!(decoded, result);
        let _ = BoardFilter::default();
    }
}
