use async_trait::async_trait;

use crate::application::ports::CookieProvider;
use crate::domain::{AuthCookies, Result};

pub struct GrpcCookieProvider {
    addr: String,
}

impl GrpcCookieProvider {
    pub fn new(addr: impl Into<String>) -> Self {
        Self { addr: addr.into() }
    }
}

#[async_trait]
impl CookieProvider for GrpcCookieProvider {
    async fn cookies(&self) -> Result<AuthCookies> {
        let _ = &self.addr;
        todo!("gRPC-клиент к auth-worker CookieService.GetCookies")
    }
}
