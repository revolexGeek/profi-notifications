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
        let _ = (&self.cookies, &self.board, &self.publisher, &request);
        todo!(
            "реализуется по TDD: cookies -> выборка доски (с пагинацией) -> маппинг -> публикация"
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::application::ports::{MockBoardSource, MockCookieProvider, MockResultPublisher};

    #[test]
    fn builds_with_mocked_ports() {
        let use_case = ProcessParseRequest::new(
            MockCookieProvider::new(),
            MockBoardSource::new(),
            MockResultPublisher::new(),
        );
        let _ = use_case;
    }
}
