package domain

// CookieFileError signals that the cookie source could not be read or is
// structurally invalid. It maps to the "missing_or_invalid_cookies" state.
type CookieFileError struct {
	Message string
}

func (e *CookieFileError) Error() string {
	return e.Message
}

// AuthExpiredError signals that the session can no longer be renewed
// automatically and a manual login is required. It maps to "requires_login".
type AuthExpiredError struct {
	Message string
}

func (e *AuthExpiredError) Error() string {
	return e.Message
}

// RenewFailedError signals that the renew endpoint answered but did not deliver
// usable tokens. It carries the token state observed at failure time so the
// caller can report it without re-reading anything.
type RenewFailedError struct {
	Message  string
	TokenTTL *int64
	Tokens   []TokenDetail
}

func (e *RenewFailedError) Error() string {
	return e.Message
}

// RenewNetworkError signals that the renew request could not complete due to a
// transport failure. Timeout distinguishes a deadline breach from other network
// faults, mirroring the distinct states the worker reports for each.
type RenewNetworkError struct {
	Err     error
	Timeout bool
}

func (e *RenewNetworkError) Error() string {
	return e.Err.Error()
}

func (e *RenewNetworkError) Unwrap() error {
	return e.Err
}
