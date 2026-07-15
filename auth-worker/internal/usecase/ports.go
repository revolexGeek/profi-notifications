// Package usecase holds the application business rules: it orchestrates the
// domain entities to keep the session fresh. It defines the ports (interfaces)
// it needs from the outside world; the adapter layer implements them. Source
// dependencies point inward — this package imports domain, never an adapter.
package usecase

import "auth-worker/internal/domain"

// CookieStore loads and persists the cookie jar together with its source URL.
type CookieStore interface {
	Load() (jar *domain.Jar, url string, err error)
	Save(jar *domain.Jar, url string) error
}

// RenewOutcome reports observable facts about a completed renew request.
type RenewOutcome struct {
	// ResponseCookieNames are the cookie names the server set on the response,
	// used to enrich diagnostics when a renew fails to refresh tokens.
	ResponseCookieNames []string
}

// SessionRenewer calls the renew endpoint using the jar's cookies and merges
// any refreshed cookies back into the jar. It returns a domain error
// (AuthExpiredError, RenewNetworkError, ...) describing recoverable failures.
type SessionRenewer interface {
	Renew(jar *domain.Jar) (RenewOutcome, error)
}

// StatusReporter persists the outcome of an auth cycle.
type StatusReporter interface {
	Report(report domain.StatusReport) error
}

// Locker guards the cookie jar against concurrent writers. Acquire blocks up to
// an implementation-defined timeout and returns a release function.
type Locker interface {
	Acquire() (release func() error, err error)
}

// Clock supplies the current unix time in seconds, injected so time-dependent
// rules stay deterministic under test.
type Clock interface {
	Now() int64
}
