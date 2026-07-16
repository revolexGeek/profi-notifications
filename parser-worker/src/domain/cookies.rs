#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AuthCookies {
    /// Строка для заголовка `Cookie`: "name=value; ...".
    pub header: String,
    pub status: String,
}
