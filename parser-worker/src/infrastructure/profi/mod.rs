mod dto;
mod mapping;
mod request;

use async_trait::async_trait;

use crate::application::ports::BoardSource;
use crate::domain::{AuthCookies, BoardFilter, BoardPage, ParserError, Result};
use dto::GraphqlResponse;

const USER_AGENT: &str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) \
     AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36";

const HEADERS: &[(&str, &str)] = &[
    ("accept", "application/json"),
    ("user-agent", USER_AGENT),
    ("origin", "https://profi.ru"),
    ("referer", "https://profi.ru/backoffice/n.php"),
    ("x-app-id", "BO"),
    ("x-new-auth-compatible", "1"),
    ("x-requested-with", "XMLHttpRequest"),
    ("x-warp-ui-app", "WEBBO"),
    ("x-warp-ui-type", "WEB"),
    ("x-warp-ui-ver", "1.0"),
];

pub struct ProfiBoardSource {
    client: reqwest::Client,
    graphql_url: String,
}

impl ProfiBoardSource {
    pub fn new(graphql_url: impl Into<String>) -> Self {
        Self {
            client: reqwest::Client::new(),
            graphql_url: graphql_url.into(),
        }
    }
}

#[async_trait]
impl BoardSource for ProfiBoardSource {
    async fn fetch(
        &self,
        filter: &BoardFilter,
        cursor: Option<String>,
        cookies: &AuthCookies,
    ) -> Result<BoardPage> {
        let body = request::build_body(filter, cursor.as_deref());

        let mut builder = self
            .client
            .post(&self.graphql_url)
            .header("cookie", &cookies.header)
            .json(&body);
        for (name, value) in HEADERS {
            builder = builder.header(*name, *value);
        }

        let response = builder
            .send()
            .await
            .map_err(|error| ParserError::Board(error.to_string()))?;
        let status = response.status();
        let text = response
            .text()
            .await
            .map_err(|error| ParserError::Board(error.to_string()))?;

        if status == reqwest::StatusCode::UNAUTHORIZED || status == reqwest::StatusCode::FORBIDDEN {
            return Err(ParserError::Auth(format!(
                "profi.ru отклонил запрос: HTTP {status}"
            )));
        }
        if !status.is_success() {
            return Err(ParserError::Board(format!("profi.ru вернул HTTP {status}")));
        }

        let parsed: GraphqlResponse =
            serde_json::from_str(&text).map_err(|error| ParserError::Decode(error.to_string()))?;

        if !parsed.errors.is_empty() {
            let messages = parsed
                .errors
                .iter()
                .map(|error| error.message.as_str())
                .collect::<Vec<_>>()
                .join("; ");
            return Err(ParserError::Board(format!("GraphQL ошибки: {messages}")));
        }

        let data = parsed
            .data
            .ok_or_else(|| ParserError::Board("ответ без поля data".to_string()))?;
        Ok(mapping::to_board_page(data.board))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use wiremock::matchers::{header, method, path};
    use wiremock::{Mock, MockServer, ResponseTemplate};

    fn cookies() -> AuthCookies {
        AuthCookies {
            header: "prfr_bo_tkn=abc".to_string(),
            status: "ok".to_string(),
        }
    }

    async fn mock_server(status: u16, body: &str) -> MockServer {
        let server = MockServer::start().await;
        Mock::given(method("POST"))
            .and(path("/graphql"))
            .respond_with(ResponseTemplate::new(status).set_body_string(body))
            .mount(&server)
            .await;
        server
    }

    #[tokio::test]
    async fn fetch_maps_snippets_and_sends_cookie() {
        let server = MockServer::start().await;
        let body = r#"{"data":{"boSearchBoardItems":{"nextCursor":"C==","serverTs":1,"totalCount":2,"items":[{"id":"1","type":"SNIPPET","title":"T","clientInfo":{"name":"N"}}]}}}"#;
        Mock::given(method("POST"))
            .and(path("/graphql"))
            .and(header("cookie", "prfr_bo_tkn=abc"))
            .and(header("x-app-id", "BO"))
            .respond_with(ResponseTemplate::new(200).set_body_string(body))
            .mount(&server)
            .await;

        let source = ProfiBoardSource::new(format!("{}/graphql", server.uri()));
        let page = source
            .fetch(&BoardFilter::default(), None, &cookies())
            .await
            .expect("ok");

        assert_eq!(page.orders.len(), 1);
        assert_eq!(page.orders[0].id, "1");
        assert_eq!(page.total_count, 2);
        assert_eq!(page.next_cursor.as_deref(), Some("C=="));
    }

    #[tokio::test]
    async fn fetch_surfaces_graphql_errors() {
        let server = mock_server(200, r#"{"errors":[{"message":"boom"}],"data":null}"#).await;
        let source = ProfiBoardSource::new(format!("{}/graphql", server.uri()));

        let error = source
            .fetch(&BoardFilter::default(), None, &cookies())
            .await
            .unwrap_err();

        assert!(matches!(error, ParserError::Board(_)));
    }

    #[tokio::test]
    async fn fetch_maps_unauthorized_to_auth_error() {
        let server = mock_server(401, "denied").await;
        let source = ProfiBoardSource::new(format!("{}/graphql", server.uri()));

        let error = source
            .fetch(&BoardFilter::default(), None, &cookies())
            .await
            .unwrap_err();

        assert!(matches!(error, ParserError::Auth(_)));
    }
}
