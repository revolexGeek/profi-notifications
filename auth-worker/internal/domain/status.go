package domain

// Status is the lifecycle state the auth-worker reports after each cycle.
type Status string

const (
	StatusOK             Status = "ok"
	StatusRenewFailed    Status = "renew_failed"
	StatusRequiresLogin  Status = "requires_login"
	StatusMissingCookies Status = "missing_or_invalid_cookies"
	StatusNetworkTimeout Status = "network_timeout"
	StatusNetworkError   Status = "network_error"
	StatusError          Status = "error"
)

// StatusReport is the outcome of a single auth cycle, ready to be persisted by
// a StatusReporter. It crosses the boundary as a plain data structure.
type StatusReport struct {
	Status    Status
	UpdatedAt int64
	TokenTTL  *int64
	Refreshed bool
	Error     string
	Tokens    []TokenDetail
}
