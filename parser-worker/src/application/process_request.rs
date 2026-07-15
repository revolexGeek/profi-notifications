use crate::application::ports::{BoardSource, CookieProvider, ResultPublisher};
use crate::domain::{ParseRequest, ParseResult, Result};

pub struct ProcessParseRequest<C, B, P> {
    cookies: C,
    board: B,
    publisher: P,
}

impl<C, B, P> ProcessParseRequest<C, B, P>
where
    C: CookieProvider,
    B: BoardSource,
    P: ResultPublisher,
{
    pub fn new(cookies: C, board: B, publisher: P) -> Self {
        Self {
            cookies,
            board,
            publisher,
        }
    }

    pub async fn execute(&self, request: ParseRequest) -> Result<ParseResult> {
        let cookies = self.cookies.cookies().await?;
        let max_pages = request.max_pages.unwrap_or(1).max(1);

        let mut orders = Vec::new();
        let mut cursor: Option<String> = None;
        let mut total_count = 0;
        let mut fetched_at = 0;

        for page_index in 0..max_pages {
            let page = self
                .board
                .fetch(&request.filter, cursor.clone(), &cookies)
                .await?;

            if page_index == 0 {
                total_count = page.total_count;
                fetched_at = page.server_ts;
            }
            orders.extend(page.orders);
            cursor = page.next_cursor;

            if cursor.is_none() {
                break;
            }
        }

        let result = ParseResult {
            request_id: request.request_id,
            fetched_at,
            total_count,
            next_cursor: cursor,
            orders,
        };

        self.publisher.publish(&result).await?;
        Ok(result)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::application::ports::{MockBoardSource, MockCookieProvider, MockResultPublisher};
    use crate::domain::{AuthCookies, BoardFilter, BoardPage, Client, Geo, Order, ParserError};

    fn cookies() -> AuthCookies {
        AuthCookies {
            header: "prfr_bo_tkn=abc".to_string(),
            status: "ok".to_string(),
        }
    }

    fn order(id: &str) -> Order {
        Order {
            id: id.to_string(),
            title: "t".to_string(),
            description: "d".to_string(),
            price: None,
            geo: Geo::default(),
            client: Client {
                name: "n".to_string(),
                tags: vec![],
            },
            badges: vec![],
            schedule: None,
            last_update: 0,
            score: 0.0,
            is_fresh: false,
            is_viewed: false,
            coordinates: None,
        }
    }

    fn page(orders: Vec<Order>, next_cursor: Option<&str>, total: u32) -> BoardPage {
        BoardPage {
            orders,
            next_cursor: next_cursor.map(str::to_string),
            total_count: total,
            server_ts: 1_700_000_000,
        }
    }

    fn request(max_pages: Option<u32>) -> ParseRequest {
        ParseRequest {
            request_id: "req-1".to_string(),
            filter: BoardFilter::default(),
            max_pages,
        }
    }

    fn expect_cookies(mock: &mut MockCookieProvider) {
        mock.expect_cookies().returning(|| Ok(cookies()));
    }

    #[tokio::test]
    async fn fetches_single_page_and_publishes() {
        let mut provider = MockCookieProvider::new();
        expect_cookies(&mut provider);

        let mut board = MockBoardSource::new();
        board
            .expect_fetch()
            .times(1)
            .returning(|_, _, _| Ok(page(vec![order("1"), order("2")], None, 28)));

        let mut publisher = MockResultPublisher::new();
        publisher
            .expect_publish()
            .withf(|result| result.orders.len() == 2 && result.total_count == 28)
            .times(1)
            .returning(|_| Ok(()));

        let result = ProcessParseRequest::new(provider, board, publisher)
            .execute(request(None))
            .await
            .expect("ok");

        assert_eq!(result.request_id, "req-1");
        assert_eq!(result.orders.len(), 2);
        assert_eq!(result.total_count, 28);
        assert!(result.next_cursor.is_none());
    }

    #[tokio::test]
    async fn follows_cursor_across_pages() {
        let mut provider = MockCookieProvider::new();
        expect_cookies(&mut provider);

        let mut board = MockBoardSource::new();
        board.expect_fetch().times(2).returning(|_, cursor, _| {
            if cursor.is_none() {
                Ok(page(vec![order("1")], Some("c1"), 3))
            } else {
                Ok(page(vec![order("2")], None, 3))
            }
        });

        let mut publisher = MockResultPublisher::new();
        publisher.expect_publish().returning(|_| Ok(()));

        let result = ProcessParseRequest::new(provider, board, publisher)
            .execute(request(Some(2)))
            .await
            .expect("ok");

        assert_eq!(result.orders.len(), 2);
        assert_eq!(result.orders[1].id, "2");
        assert!(result.next_cursor.is_none());
    }

    #[tokio::test]
    async fn stops_paginating_when_cursor_exhausted() {
        let mut provider = MockCookieProvider::new();
        expect_cookies(&mut provider);

        let mut board = MockBoardSource::new();
        board
            .expect_fetch()
            .times(1)
            .returning(|_, _, _| Ok(page(vec![order("1")], None, 1)));

        let mut publisher = MockResultPublisher::new();
        publisher.expect_publish().returning(|_| Ok(()));

        let result = ProcessParseRequest::new(provider, board, publisher)
            .execute(request(Some(5)))
            .await
            .expect("ok");

        assert_eq!(result.orders.len(), 1);
    }

    #[tokio::test]
    async fn fails_without_fetching_when_cookies_unavailable() {
        let mut provider = MockCookieProvider::new();
        provider
            .expect_cookies()
            .returning(|| Err(ParserError::Auth("нет сессии".to_string())));

        let mut board = MockBoardSource::new();
        board.expect_fetch().never();

        let publisher = MockResultPublisher::new();

        let error = ProcessParseRequest::new(provider, board, publisher)
            .execute(request(None))
            .await
            .unwrap_err();

        assert!(matches!(error, ParserError::Auth(_)));
    }

    #[tokio::test]
    async fn propagates_publish_error() {
        let mut provider = MockCookieProvider::new();
        expect_cookies(&mut provider);

        let mut board = MockBoardSource::new();
        board
            .expect_fetch()
            .returning(|_, _, _| Ok(page(vec![order("1")], None, 1)));

        let mut publisher = MockResultPublisher::new();
        publisher
            .expect_publish()
            .returning(|_| Err(ParserError::Publish("очередь недоступна".to_string())));

        let error = ProcessParseRequest::new(provider, board, publisher)
            .execute(request(None))
            .await
            .unwrap_err();

        assert!(matches!(error, ParserError::Publish(_)));
    }
}
