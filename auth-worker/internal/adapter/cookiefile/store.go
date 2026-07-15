// Package cookiefile implements usecase.CookieStore over a JSON file in the
// browser cookie-export format. It maps the on-disk shape to and from domain
// cookies, keeping that format detail out of the inner layers.
package cookiefile

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"os"

	"auth-worker/internal/domain"
	"auth-worker/internal/platform/atomicjson"
)

// Store reads and writes the cookie jar from a single JSON file.
type Store struct {
	path string
}

// New creates a Store bound to the given file path.
func New(path string) *Store {
	return &Store{path: path}
}

// Load reads the cookie file and returns the jar and its source URL. Missing or
// invalid files surface as *domain.CookieFileError.
func (s *Store) Load() (*domain.Jar, string, error) {
	data, err := os.ReadFile(s.path)
	if err != nil {
		return nil, "", s.readError(err)
	}

	export, err := parseExport(data)
	if err != nil {
		return nil, "", err
	}

	jar := jarFromExport(export)
	if jar.Len() == 0 {
		return nil, "", &domain.CookieFileError{Message: "cookies.json contains no valid cookies"}
	}

	return jar, export.URL, nil
}

// Save writes the jar back to the cookie file atomically.
func (s *Store) Save(jar *domain.Jar, url string) error {
	return atomicjson.Write(s.path, exportFrom(jar, url))
}

func (s *Store) readError(err error) error {
	if errors.Is(err, os.ErrNotExist) {
		return &domain.CookieFileError{Message: fmt.Sprintf("cookie file not found: %s", s.path)}
	}
	return &domain.CookieFileError{Message: fmt.Sprintf("could not read cookie file: %v", err)}
}

// parseExport accepts either an object with a "cookies" array or a bare array of
// cookies, mirroring the formats the Python worker tolerated.
func parseExport(data []byte) (browserExport, error) {
	trimmed := bytes.TrimSpace(data)
	if len(trimmed) == 0 {
		return browserExport{}, &domain.CookieFileError{Message: "cookie file is empty"}
	}

	if trimmed[0] == '[' {
		return parseCookieArray(trimmed)
	}
	return parseCookieObject(trimmed)
}

func parseCookieArray(data []byte) (browserExport, error) {
	var cookies []browserCookie
	if err := json.Unmarshal(data, &cookies); err != nil {
		return browserExport{}, invalidJSON(err)
	}
	return browserExport{URL: defaultURL, Cookies: cookies}, nil
}

func parseCookieObject(data []byte) (browserExport, error) {
	var raw struct {
		URL     string          `json:"url"`
		Cookies json.RawMessage `json:"cookies"`
	}
	if err := json.Unmarshal(data, &raw); err != nil {
		return browserExport{}, invalidJSON(err)
	}

	if len(raw.Cookies) == 0 {
		return browserExport{}, &domain.CookieFileError{Message: `cookie file has no "cookies" array`}
	}

	var cookies []browserCookie
	if err := json.Unmarshal(raw.Cookies, &cookies); err != nil {
		return browserExport{}, &domain.CookieFileError{Message: `"cookies" must be an array`}
	}

	return browserExport{URL: orDefault(raw.URL, defaultURL), Cookies: cookies}, nil
}

func jarFromExport(export browserExport) *domain.Jar {
	cookies := make([]domain.Cookie, 0, len(export.Cookies))
	for _, item := range export.Cookies {
		if cookie, ok := item.toDomain(); ok {
			cookies = append(cookies, cookie)
		}
	}
	return domain.NewJar(cookies)
}

func invalidJSON(err error) error {
	return &domain.CookieFileError{Message: fmt.Sprintf("invalid JSON in cookie file: %v", err)}
}
