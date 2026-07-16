package usecase

import (
	"encoding/base64"
	"fmt"
	"io"
	"log/slog"

	"auth-worker/internal/domain"
)

func discardLogger() *slog.Logger {
	return slog.New(slog.NewTextHandler(io.Discard, nil))
}

func makeJWT(exp int64) string {
	return makeJWTStatus(exp, "touched")
}

func makeJWTStatus(exp int64, status string) string {
	header := base64.RawURLEncoding.EncodeToString([]byte(`{"alg":"HS256","typ":"JWT"}`))
	payload := base64.RawURLEncoding.EncodeToString([]byte(fmt.Sprintf(`{"exp":%d,"status":%q}`, exp, status)))
	return header + "." + payload + ".signature"
}

func tokenCookie(exp int64) domain.Cookie {
	return domain.Cookie{
		Name:      "prfr_bo_tkn",
		Value:     makeJWT(exp),
		Domain:    ".profi.ru",
		Path:      "/",
		ExpiresAt: exp + 1000,
	}
}

// fixedClock returns a constant time so TTL arithmetic is deterministic.
type fixedClock struct {
	now int64
}

func (c fixedClock) Now() int64 { return c.now }

// fakeLocker records how often the lock was acquired and released.
type fakeLocker struct {
	acquireErr error
	acquired   int
	released   int
}

func (l *fakeLocker) Acquire() (func() error, error) {
	if l.acquireErr != nil {
		return nil, l.acquireErr
	}
	l.acquired++
	return func() error {
		l.released++
		return nil
	}, nil
}

// fakeStore serves a prepared jar and records saves.
type fakeStore struct {
	jar      *domain.Jar
	url      string
	loadErr  error
	saveErr  error
	saved    *domain.Jar
	saveCall int
}

func (s *fakeStore) Load() (*domain.Jar, string, error) {
	if s.loadErr != nil {
		return nil, "", s.loadErr
	}
	return s.jar, s.url, nil
}

func (s *fakeStore) Save(jar *domain.Jar, _ string) error {
	s.saveCall++
	s.saved = jar
	return s.saveErr
}

// fakeRenewer mutates the jar through onRenew to simulate the server setting
// fresh cookies, then returns the configured outcome and error.
type fakeRenewer struct {
	onRenew func(jar *domain.Jar)
	outcome RenewOutcome
	err     error
	calls   int
}

func (r *fakeRenewer) Renew(jar *domain.Jar) (RenewOutcome, error) {
	r.calls++
	if r.onRenew != nil {
		r.onRenew(jar)
	}
	return r.outcome, r.err
}

// fakeReporter captures the last status report.
type fakeReporter struct {
	reports []domain.StatusReport
}

func (r *fakeReporter) Report(report domain.StatusReport) error {
	r.reports = append(r.reports, report)
	return nil
}

func (r *fakeReporter) last() domain.StatusReport {
	return r.reports[len(r.reports)-1]
}

// fakeRefresher returns a scripted result/error for worker tests.
type fakeRefresher struct {
	result RefreshResult
	err    error
}

func (r *fakeRefresher) Execute() (RefreshResult, error) {
	return r.result, r.err
}
