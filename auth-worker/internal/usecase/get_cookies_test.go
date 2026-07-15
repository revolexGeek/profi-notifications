package usecase

import (
	"errors"
	"strings"
	"testing"

	"auth-worker/internal/domain"
)

func newGetCookies(store *fakeStore, locker *fakeLocker) *GetCookies {
	return NewGetCookies(store, locker, fixedClock{now: testNow})
}

func TestGetCookiesReportsOkForFreshToken(t *testing.T) {
	store := &fakeStore{
		jar: domain.NewJar([]domain.Cookie{
			tokenCookie(testNow + 3600),
			{Name: "sid", Value: "abc", Domain: ".profi.ru", Path: "/"},
		}),
		url: "https://profi.ru",
	}
	locker := &fakeLocker{}

	snapshot, err := newGetCookies(store, locker).Execute()

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if snapshot.Status != domain.StatusOK {
		t.Errorf("status = %q, want ok", snapshot.Status)
	}
	if !snapshot.HasToken || snapshot.TokenTTL != 3600 {
		t.Errorf("token ttl = %d has=%t, want 3600/true", snapshot.TokenTTL, snapshot.HasToken)
	}
	if !strings.Contains(snapshot.CookieHeader, "sid=abc") {
		t.Errorf("cookie header missing sid: %q", snapshot.CookieHeader)
	}
	if len(snapshot.Cookies) != 2 {
		t.Errorf("cookie count = %d, want 2", len(snapshot.Cookies))
	}
	if locker.released != 1 {
		t.Errorf("lock released %d times, want 1", locker.released)
	}
}

func TestGetCookiesReportsRequiresLoginForExpiredToken(t *testing.T) {
	store := &fakeStore{jar: domain.NewJar([]domain.Cookie{tokenCookie(testNow - 10)}), url: "https://profi.ru"}

	snapshot, err := newGetCookies(store, &fakeLocker{}).Execute()

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if snapshot.Status != domain.StatusRequiresLogin {
		t.Errorf("status = %q, want requires_login", snapshot.Status)
	}
	if !snapshot.HasToken {
		t.Error("expired token is still a token")
	}
}

func TestGetCookiesReportsRequiresLoginWithoutToken(t *testing.T) {
	store := &fakeStore{
		jar: domain.NewJar([]domain.Cookie{{Name: "sid", Value: "x", Domain: ".profi.ru", Path: "/"}}),
		url: "https://profi.ru",
	}

	snapshot, err := newGetCookies(store, &fakeLocker{}).Execute()

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if snapshot.Status != domain.StatusRequiresLogin {
		t.Errorf("status = %q, want requires_login", snapshot.Status)
	}
	if snapshot.HasToken {
		t.Error("should report no token")
	}
}

func TestGetCookiesPropagatesLoadError(t *testing.T) {
	store := &fakeStore{loadErr: &domain.CookieFileError{Message: "missing"}}

	_, err := newGetCookies(store, &fakeLocker{}).Execute()

	var cookieErr *domain.CookieFileError
	if !errors.As(err, &cookieErr) {
		t.Fatalf("error = %v, want CookieFileError", err)
	}
}
