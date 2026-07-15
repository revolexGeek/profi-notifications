package cookiefile

import (
	"errors"
	"os"
	"path/filepath"
	"testing"

	"auth-worker/internal/domain"
)

const sampleExport = `{
  "url": "https://profi.ru",
  "cookies": [
    {"domain": ".profi.ru", "name": "prfr_bo_tkn", "path": "/", "value": "token-value", "secure": true, "httpOnly": true, "sameSite": "no_restriction", "session": false, "expirationDate": 2098283343.0},
    {"domain": ".profi.ru", "name": "NEXT_LOCALE", "path": "/", "value": "msk", "sameSite": "lax", "session": true}
  ]
}`

func writeFile(t *testing.T, dir, name, content string) string {
	t.Helper()
	path := filepath.Join(dir, name)
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatalf("write fixture: %v", err)
	}
	return path
}

func TestLoadParsesObjectForm(t *testing.T) {
	path := writeFile(t, t.TempDir(), "cookies.json", sampleExport)

	jar, url, err := New(path).Load()

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if url != "https://profi.ru" {
		t.Errorf("url = %q, want https://profi.ru", url)
	}
	if jar.Len() != 2 {
		t.Fatalf("cookie count = %d, want 2", jar.Len())
	}
}

func TestLoadParsesBareArrayForm(t *testing.T) {
	array := `[{"domain": ".profi.ru", "name": "sid", "path": "/", "value": "abc", "session": true}]`
	path := writeFile(t, t.TempDir(), "cookies.json", array)

	jar, url, err := New(path).Load()

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if url != defaultURL {
		t.Errorf("url = %q, want %q", url, defaultURL)
	}
	if jar.Len() != 1 {
		t.Fatalf("cookie count = %d, want 1", jar.Len())
	}
}

func TestLoadMissingFile(t *testing.T) {
	_, _, err := New(filepath.Join(t.TempDir(), "absent.json")).Load()

	assertCookieFileError(t, err)
}

func TestLoadEmptyCookies(t *testing.T) {
	path := writeFile(t, t.TempDir(), "cookies.json", `{"url": "https://profi.ru", "cookies": []}`)

	_, _, err := New(path).Load()

	assertCookieFileError(t, err)
}

func TestLoadObjectWithoutCookiesArray(t *testing.T) {
	path := writeFile(t, t.TempDir(), "cookies.json", `{"url": "https://profi.ru"}`)

	_, _, err := New(path).Load()

	assertCookieFileError(t, err)
}

func TestSaveRoundTripPreservesCookies(t *testing.T) {
	dir := t.TempDir()
	source := writeFile(t, dir, "cookies.json", sampleExport)

	store := New(source)
	jar, url, err := store.Load()
	if err != nil {
		t.Fatalf("load: %v", err)
	}

	if err := store.Save(jar, url); err != nil {
		t.Fatalf("save: %v", err)
	}

	reloaded, _, err := store.Load()
	if err != nil {
		t.Fatalf("reload: %v", err)
	}

	token := findCookie(t, reloaded, "prfr_bo_tkn")
	if token.Value != "token-value" {
		t.Errorf("token value = %q, want token-value", token.Value)
	}
	if token.SameSite != domain.SameSiteNone {
		t.Errorf("same site = %q, want None", token.SameSite)
	}
	if token.IsSession() {
		t.Error("persistent token should not become a session cookie")
	}

	locale := findCookie(t, reloaded, "NEXT_LOCALE")
	if !locale.IsSession() {
		t.Error("session cookie should round-trip as session")
	}
}

func findCookie(t *testing.T, jar *domain.Jar, name string) domain.Cookie {
	t.Helper()
	for _, cookie := range jar.Cookies() {
		if cookie.Name == name {
			return cookie
		}
	}
	t.Fatalf("cookie %q not found", name)
	return domain.Cookie{}
}

func assertCookieFileError(t *testing.T, err error) {
	t.Helper()
	var cookieErr *domain.CookieFileError
	if !errors.As(err, &cookieErr) {
		t.Fatalf("error = %v, want CookieFileError", err)
	}
}
