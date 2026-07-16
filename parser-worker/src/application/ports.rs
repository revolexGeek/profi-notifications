use async_trait::async_trait;

use crate::domain::{AuthCookies, BoardFilter, BoardPage, ParseResult, Result};

#[cfg_attr(test, mockall::automock)]
#[async_trait]
pub trait CookieProvider: Send + Sync {
    async fn cookies(&self) -> Result<AuthCookies>;
}

#[cfg_attr(test, mockall::automock)]
#[async_trait]
pub trait BoardSource: Send + Sync {
    async fn fetch(
        &self,
        filter: &BoardFilter,
        cursor: Option<String>,
        cookies: &AuthCookies,
    ) -> Result<BoardPage>;
}

#[cfg_attr(test, mockall::automock)]
#[async_trait]
pub trait ResultPublisher: Send + Sync {
    async fn publish(&self, result: &ParseResult) -> Result<()>;
}
