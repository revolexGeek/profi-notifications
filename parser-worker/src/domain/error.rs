use thiserror::Error;

pub type Result<T, E = ParserError> = std::result::Result<T, E>;

#[derive(Debug, Error)]
pub enum ParserError {
    #[error("некорректный запрос парсинга: {0}")]
    InvalidRequest(String),

    #[error("авторизация недоступна: {0}")]
    Auth(String),

    #[error("ошибка источника заказов: {0}")]
    Board(String),

    #[error("ошибка публикации результата: {0}")]
    Publish(String),

    #[error("ошибка разбора ответа: {0}")]
    Decode(String),
}
