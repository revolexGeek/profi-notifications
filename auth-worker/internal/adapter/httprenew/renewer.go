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
	client  *http.Client
	url     string
	headers map[string]string
	log     *slog.Logger
}

// New creates a Renewer that never follows redirects, so a redirect can be
// interpreted as an expired session rather than silently chased.
func New(url string, headers map[string]string, timeout time.Duration, log *slog.Logger) *Renewer {
	client := &http.Client{
		Timeout: timeout,
		CheckRedirect: func(*http.Request, []*http.Request) error {
			return http.ErrUseLastResponse
		},
	}

	return &Renewer{client: client, url: url, headers: headers, log: log}
}

// Renew calls the renew endpoint with the jar's cookies, merges any refreshed
// cookies back into the jar, and classifies the outcome.
func (r *Renewer) Renew(jar *domain.Jar) (usecase.RenewOutcome, error) {
	r.logAuthCookies(jar, "before renew")

	response, err := r.send(jar)
	if err != nil {
		return usecase.RenewOutcome{}, err
	}
	defer response.Body.Close()

	names := mergeResponseCookies(jar, response)
	r.logResponse(response, names)

	if err := classify(response); err != nil {
		return usecase.RenewOutcome{}, err
	}

	r.logAuthCookies(jar, "after renew")
	return usecase.RenewOutcome{ResponseCookieNames: names}, nil
}

func (r *Renewer) send(jar *domain.Jar) (*http.Response, error) {
	request, err := http.NewRequestWithContext(context.Background(), http.MethodGet, r.url, nil)
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

func (r *Renewer) logResponse(response *http.Response, cookieNames []string) {
	r.log.Info("renew response",
		"status", response.StatusCode,
		"content_type", orDefault(response.Header.Get("Content-Type"), "unspecified"),
		"response_cookies", cookieNames,
	)

	body, err := io.ReadAll(io.LimitReader(response.Body, maxBodyBytes))
	if err != nil {
		r.log.Warn("could not read renew response body", "error", err)
		return
	}

	preview := redactBody(string(body))
	if preview == "" {
		r.log.Info("renew response body empty")
		return
	}
	r.log.Info("renew response body", "preview", preview)
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
