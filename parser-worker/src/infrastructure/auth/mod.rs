pub mod proto {
    tonic::include_proto!("auth.v1");
}

use async_trait::async_trait;
use tonic::transport::Channel;

use crate::application::ports::CookieProvider;
use crate::domain::{AuthCookies, ParserError, Result};
use proto::GetCookiesRequest;
use proto::cookie_service_client::CookieServiceClient;

pub struct GrpcCookieProvider {
    client: CookieServiceClient<Channel>,
}

impl GrpcCookieProvider {
    pub fn new(addr: impl Into<String>) -> Result<Self> {
        let channel = Channel::from_shared(addr.into())
            .map_err(|error| ParserError::Auth(error.to_string()))?
            .connect_lazy();
        Ok(Self {
            client: CookieServiceClient::new(channel),
        })
    }
}

#[async_trait]
impl CookieProvider for GrpcCookieProvider {
    async fn cookies(&self) -> Result<AuthCookies> {
        let response = self
            .client
            .clone()
            .get_cookies(GetCookiesRequest {})
            .await
            .map_err(|status| ParserError::Auth(status.message().to_string()))?
            .into_inner();

        Ok(AuthCookies {
            header: response.cookie_header,
            status: response.status,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use proto::cookie_service_server::{CookieService, CookieServiceServer};
    use proto::{GetCookiesRequest, GetCookiesResponse};
    use tokio::net::TcpListener;
    use tokio_stream::wrappers::TcpListenerStream;
    use tonic::transport::Server;
    use tonic::{Request, Response, Status};

    struct FakeCookies;

    #[tonic::async_trait]
    impl CookieService for FakeCookies {
        async fn get_cookies(
            &self,
            _request: Request<GetCookiesRequest>,
        ) -> std::result::Result<Response<GetCookiesResponse>, Status> {
            Ok(Response::new(GetCookiesResponse {
                cookies: vec![],
                cookie_header: "prfr_bo_tkn=abc; sid=x".to_string(),
                status: "ok".to_string(),
                token_ttl: 120,
                has_token: true,
            }))
        }
    }

    #[tokio::test]
    async fn fetches_cookies_over_grpc() {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let addr = listener.local_addr().unwrap();
        tokio::spawn(async move {
            Server::builder()
                .add_service(CookieServiceServer::new(FakeCookies))
                .serve_with_incoming(TcpListenerStream::new(listener))
                .await
                .unwrap();
        });

        let provider = GrpcCookieProvider::new(format!("http://{addr}")).unwrap();
        let cookies = provider.cookies().await.expect("cookies");

        assert_eq!(cookies.header, "prfr_bo_tkn=abc; sid=x");
        assert_eq!(cookies.status, "ok");
    }
}
