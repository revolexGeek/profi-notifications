package httprenew

import (
	"encoding/base64"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"auth-worker/internal/domain"
)

func makeJWT(exp int64) string {
	header := base64.RawURLEncoding.EncodeToString([]byte(`{"alg":"HS256","typ":"JWT"}`))
	payload := base64.RawURLEncoding.EncodeToString([]byte(fmt.Sprintf(`{"exp":%d}`, exp)))
	return header + "." + payload + ".signature"
}

func discardLogger() *slog.Logger {
	return slog.New(slog.NewTextHandler(io.Discard, nil))
}

func newRenewer(t *testing.T, url string, timeout time.Duration) *Renewer {
	t.Helper()
	return New(url, url, map[string]string{"x-app-id": "BO"}, timeout, discardLogger())
}

func jarWithToken(exp int64) *domain.Jar {
	return domain.NewJar([]domain.Cookie{{
		Name:   "prfr_bo_tkn",
		Value:  makeJWT(exp),
		Domain: ".profi.ru",
		Path:   "/",
	}})
}

func TestRenewMergesRefreshedCookies(t *testing.T) {
	freshToken := makeJWT(time.Now().Unix() + 7200)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		http.SetCookie(w, &http.Cookie{Name: "prfr_bo_tkn", Value: freshToken, Path: "/", Domain: ".profi.ru"})
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	jar := jarWithToken(time.Now().Unix() + 60)

	outcome, err := newRenewer(t, server.URL, 5*time.Second).Renew(jar)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(outcome.ResponseCookieNames) != 1 || outcome.ResponseCookieNames[0] != "prfr_bo_tkn" {
		t.Errorf("response cookies = %v, want [prfr_bo_tkn]", outcome.ResponseCookieNames)
	}
	latest := jar.LatestTokens()["prfr_bo_tkn"]
	if latest.Cookie.Value != freshToken {
		t.Error("jar was not updated with the refreshed token")
	}
}

func TestRenewTreatsUnauthorizedAsExpired(t *testing.T) {
	server := statusServer(t, http.StatusUnauthorized, nil)
	defer server.Close()

	_, err := newRenewer(t, server.URL, 5*time.Second).Renew(jarWithToken(time.Now().Unix() + 60))

	var expired *domain.AuthExpiredError
	if !errors.As(err, &expired) {
		t.Fatalf("error = %v, want AuthExpiredError", err)
	}
}

func TestRenewTreatsRedirectAsExpired(t *testing.T) {
	server := statusServer(t, http.StatusFound, map[string]string{"Location": "https://profi.ru/login"})
	defer server.Close()

	_, err := newRenewer(t, server.URL, 5*time.Second).Renew(jarWithToken(time.Now().Unix() + 60))

	var expired *domain.AuthExpiredError
	if !errors.As(err, &expired) {
		t.Fatalf("error = %v, want AuthExpiredError", err)
	}
}

func TestRenewServerErrorIsNetworkError(t *testing.T) {
	server := statusServer(t, http.StatusInternalServerError, nil)
	defer server.Close()

	_, err := newRenewer(t, server.URL, 5*time.Second).Renew(jarWithToken(time.Now().Unix() + 60))

	var network *domain.RenewNetworkError
	if !errors.As(err, &network) {
		t.Fatalf("error = %v, want RenewNetworkError", err)
	}
	if network.Timeout {
		t.Error("a 500 response should not be classified as a timeout")
	}
}

func TestRenewRateLimitIsGenericError(t *testing.T) {
	server := statusServer(t, http.StatusTooManyRequests, map[string]string{"Retry-After": "30"})
	defer server.Close()

	_, err := newRenewer(t, server.URL, 5*time.Second).Renew(jarWithToken(time.Now().Unix() + 60))

	if err == nil {
		t.Fatal("expected an error for HTTP 429")
	}
	var expired *domain.AuthExpiredError
	var network *domain.RenewNetworkError
	if errors.As(err, &expired) || errors.As(err, &network) {
		t.Fatalf("429 should be a generic error, got %v", err)
	}
}

func TestRenewTimeoutIsClassified(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		time.Sleep(200 * time.Millisecond)
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	_, err := newRenewer(t, server.URL, 30*time.Millisecond).Renew(jarWithToken(time.Now().Unix() + 60))

	var network *domain.RenewNetworkError
	if !errors.As(err, &network) {
		t.Fatalf("error = %v, want RenewNetworkError", err)
	}
	if !network.Timeout {
		t.Error("a client timeout should be classified as a timeout")
	}
}

func statusServer(t *testing.T, code int, headers map[string]string) *httptest.Server {
	t.Helper()
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		for key, value := range headers {
			w.Header().Set(key, value)
		}
		w.WriteHeader(code)
	}))
}

func TestRenewCallsRenewThenTouch(t *testing.T) {
	renewToken := makeJWT(time.Now().Unix() + 3600)
	touchToken := makeJWT(time.Now().Unix() + 7200)
	var hits []string
	mux := http.NewServeMux()
	mux.HandleFunc("/auth/token/renew", func(w http.ResponseWriter, _ *http.Request) {
		hits = append(hits, "renew")
		http.SetCookie(w, &http.Cookie{Name: "prfr_bo_tkn", Value: renewToken, Path: "/", Domain: ".profi.ru"})
		w.WriteHeader(http.StatusOK)
	})
	mux.HandleFunc("/auth/token/touch", func(w http.ResponseWriter, _ *http.Request) {
		hits = append(hits, "touch")
		http.SetCookie(w, &http.Cookie{Name: "prfr_bo_tkn", Value: touchToken, Path: "/", Domain: ".profi.ru"})
		w.WriteHeader(http.StatusOK)
	})
	server := httptest.NewServer(mux)
	defer server.Close()

	renewer := New(server.URL+"/auth/token/renew", server.URL+"/auth/token/touch", map[string]string{"x-app-id": "BO"}, 5*time.Second, discardLogger())
	jar := jarWithToken(time.Now().Unix() + 60)

	if _, err := renewer.Renew(jar); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(hits) != 2 || hits[0] != "renew" || hits[1] != "touch" {
		t.Fatalf("call order = %v, want [renew touch]", hits)
	}
	if got := jar.LatestTokens()["prfr_bo_tkn"].Cookie.Value; got != touchToken {
		t.Error("jar should end with the touched token")
	}
}
