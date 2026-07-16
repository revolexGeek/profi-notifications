// Package httprenew implements usecase.SessionRenewer over HTTP. It confines
// net/http, header details, and status-code interpretation to the edge,
// translating transport outcomes into domain errors.
package httprenew

import (
	"context"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net"
	"net/http"
	"sort"
	"time"

	"auth-worker/internal/domain"
	"auth-worker/internal/usecase"
)

const maxBodyBytes = 64 * 1024

var (
	authRejectedCodes = map[int]struct{}{
		http.StatusUnauthorized: {},
		http.StatusForbidden:    {},
	}
	redirectCodes = map[int]struct{}{
		http.StatusMovedPermanently:  {},
		http.StatusFound:             {},
		http.StatusSeeOther:          {},
		http.StatusTemporaryRedirect: {},
		http.StatusPermanentRedirect: {},
	}
)

// Renewer performs the renew request against the configured endpoint.
type Renewer struct {
	client   *http.Client
	renewURL string
	touchURL string
	headers  map[string]string
	log      *slog.Logger
}

// New creates a Renewer that never follows redirects, so a redirect can be
// interpreted as an expired session rather than silently chased.
func New(renewURL, touchURL string, headers map[string]string, timeout time.Duration, log *slog.Logger) *Renewer {
	client := &http.Client{
		Timeout: timeout,
		CheckRedirect: func(*http.Request, []*http.Request) error {
			return http.ErrUseLastResponse
		},
	}

	return &Renewer{client: client, renewURL: renewURL, touchURL: touchURL, headers: headers, log: log}
}

// Renew refreshes the session in two steps, mirroring the profi.ru frontend:
// the renew call issues a fresh token with status "renew", and the touch call
// upgrades it to "touched" — the state the board requires.
func (r *Renewer) Renew(jar *domain.Jar) (usecase.RenewOutcome, error) {
	r.logAuthCookies(jar, "before renew")

	renewNames, err := r.step(jar, r.renewURL, "renew")
	if err != nil {
		return usecase.RenewOutcome{}, err
	}

	touchNames := r.tryTouch(jar)

	r.logAuthCookies(jar, "after renew")
	return usecase.RenewOutcome{ResponseCookieNames: mergeNames(renewNames, touchNames)}, nil
}

// tryTouch upgrades the freshly renewed token to "touched" status — the state
// the backoffice board requires. touch only succeeds while the login session
// is still valid, so a failure here signals a stale session rather than a
// broken renewal. The renewed token is already saved, so the failure is logged
// and swallowed to keep the loop alive until the session is refreshed.
func (r *Renewer) tryTouch(jar *domain.Jar) []string {
	names, err := r.step(jar, r.touchURL, "touch")
	if err != nil {
		r.log.Warn("touch step failed, keeping renewed token", "error", err)
		return nil
	}
	return names
}

func (r *Renewer) step(jar *domain.Jar, url, label string) ([]string, error) {
	response, err := r.send(jar, url)
	if err != nil {
		return nil, err
	}
	defer response.Body.Close()

	names := mergeResponseCookies(jar, response)
	r.logResponse(label, response, names)

	if err := classify(response); err != nil {
		return nil, err
	}
	return names, nil
}

func (r *Renewer) send(jar *domain.Jar, url string) (*http.Response, error) {
	request, err := http.NewRequestWithContext(context.Background(), http.MethodGet, url, nil)
	if err != nil {
		return nil, err
	}

	for key, value := range r.headers {
		request.Header.Set(key, value)
	}
	request.Header.Set("Cookie", cookieHeader(jar))

	response, err := r.client.Do(request)
	if err != nil {
		return nil, &domain.RenewNetworkError{Err: err, Timeout: isTimeout(err)}
	}

	return response, nil
}

func mergeNames(first, second []string) []string {
	seen := make(map[string]struct{})
	var out []string
	for _, group := range [][]string{first, second} {
		for _, name := range group {
			if _, ok := seen[name]; ok {
				continue
			}
			seen[name] = struct{}{}
			out = append(out, name)
		}
	}
	sort.Strings(out)
	return out
}

// classify maps a completed response to a domain error, or nil on success.
func classify(response *http.Response) error {
	code := response.StatusCode

	if _, rejected := authRejectedCodes[code]; rejected {
		return &domain.AuthExpiredError{
			Message: fmt.Sprintf("profi.ru rejected the renew request: HTTP %d", code),
		}
	}

	if _, redirect := redirectCodes[code]; redirect {
		location := orDefault(response.Header.Get("Location"), "no Location header")
		return &domain.AuthExpiredError{
			Message: fmt.Sprintf("renew returned a redirect: %s", location),
		}
	}

	if code == http.StatusTooManyRequests {
		retryAfter := orDefault(response.Header.Get("Retry-After"), "unspecified")
		return fmt.Errorf("profi.ru rate limited the renew request: Retry-After=%s", retryAfter)
	}

	if code >= http.StatusBadRequest {
		return &domain.RenewNetworkError{
			Err:     fmt.Errorf("renew returned HTTP %d", code),
			Timeout: false,
		}
	}

	return nil
}

func isTimeout(err error) bool {
	var netErr net.Error
	if errors.As(err, &netErr) && netErr.Timeout() {
		return true
	}
	return errors.Is(err, context.DeadlineExceeded)
}

func (r *Renewer) logResponse(label string, response *http.Response, cookieNames []string) {
	r.log.Info(label+" response",
		"status", response.StatusCode,
		"content_type", orDefault(response.Header.Get("Content-Type"), "unspecified"),
		"response_cookies", cookieNames,
	)

	body, err := io.ReadAll(io.LimitReader(response.Body, maxBodyBytes))
	if err != nil {
		r.log.Warn("could not read response body", "error", err, "step", label)
		return
	}

	preview := redactBody(string(body))
	if preview == "" {
		return
	}
	r.log.Info(label+" response body", "preview", preview)
}

func (r *Renewer) logAuthCookies(jar *domain.Jar, label string) {
	cookies := jar.AuthCookies()
	if len(cookies) == 0 {
		r.log.Warn("no auth cookies found", "phase", label)
		return
	}

	now := time.Now().Unix()
	for _, cookie := range cookies {
		r.log.Info("auth cookie",
			"phase", label,
			"name", cookie.Name,
			"domain", cookie.Domain,
			"path", cookie.Path,
			"secure", cookie.Secure,
			"fingerprint", domain.Fingerprint(cookie.Value),
			"jwt_ttl", jwtTTL(cookie, now),
		)
	}
}

func jwtTTL(cookie domain.Cookie, now int64) any {
	if !domain.IsTokenCookie(cookie.Name) {
		return nil
	}
	if expiration, ok := domain.DecodeJWTExp(cookie.Value); ok {
		return expiration - now
	}
	return nil
}
