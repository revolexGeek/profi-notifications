package cookiefile

import (
	"sort"
	"strings"

	"auth-worker/internal/domain"
)

const (
	defaultURL    = "https://profi.ru"
	defaultDomain = ".profi.ru"
	defaultPath   = "/"
	defaultStore  = "0"
)

// browserExport is the on-disk JSON shape produced by browser cookie exports.
type browserExport struct {
	URL     string          `json:"url"`
	Cookies []browserCookie `json:"cookies"`
}

// browserCookie mirrors a single entry in a browser cookie export.
type browserCookie struct {
	Domain         string   `json:"domain"`
	HostOnly       bool     `json:"hostOnly"`
	HTTPOnly       bool     `json:"httpOnly"`
	Name           string   `json:"name"`
	Path           string   `json:"path"`
	SameSite       string   `json:"sameSite"`
	Secure         bool     `json:"secure"`
	Session        bool     `json:"session"`
	StoreID        string   `json:"storeId"`
	Value          string   `json:"value"`
	ExpirationDate *float64 `json:"expirationDate,omitempty"`
}

// toDomain converts a browser cookie into a domain cookie, or returns false if
// it lacks a usable name.
func (b browserCookie) toDomain() (domain.Cookie, bool) {
	if b.Name == "" {
		return domain.Cookie{}, false
	}

	cookie := domain.Cookie{
		Name:     b.Name,
		Value:    b.Value,
		Domain:   orDefault(b.Domain, defaultDomain),
		Path:     orDefault(b.Path, defaultPath),
		Secure:   b.Secure,
		HTTPOnly: b.HTTPOnly,
		HostOnly: b.HostOnly,
		Session:  b.Session,
		SameSite: sameSiteFromBrowser(b.SameSite),
	}

	if !b.Session && b.ExpirationDate != nil {
		cookie.ExpiresAt = int64(*b.ExpirationDate)
	}

	return cookie, true
}

// browserCookieFrom converts a domain cookie back into the browser export shape.
func browserCookieFrom(cookie domain.Cookie) browserCookie {
	session := cookie.IsSession()

	item := browserCookie{
		Domain:   cookie.Domain,
		HostOnly: cookie.HostOnly,
		HTTPOnly: cookie.HTTPOnly,
		Name:     cookie.Name,
		Path:     orDefault(cookie.Path, defaultPath),
		SameSite: sameSiteToBrowser(cookie.SameSite),
		Secure:   cookie.Secure,
		Session:  session,
		StoreID:  defaultStore,
		Value:    cookie.Value,
	}

	if !session && cookie.ExpiresAt != 0 {
		expires := float64(cookie.ExpiresAt)
		item.ExpirationDate = &expires
	}

	return item
}

// exportFrom builds a sorted browser export from a jar.
func exportFrom(jar *domain.Jar, url string) browserExport {
	cookies := make([]browserCookie, 0, jar.Len())
	for _, cookie := range jar.Cookies() {
		cookies = append(cookies, browserCookieFrom(cookie))
	}

	sort.Slice(cookies, func(a, b int) bool {
		return lessByLocation(cookies[a], cookies[b])
	})

	return browserExport{URL: url, Cookies: cookies}
}

func lessByLocation(a, b browserCookie) bool {
	if a.Domain != b.Domain {
		return a.Domain < b.Domain
	}
	if a.Path != b.Path {
		return a.Path < b.Path
	}
	return a.Name < b.Name
}

// sameSiteFromBrowser normalises a browser SameSite value into the canonical
// domain form. Unknown or unspecified values collapse to Unspecified.
func sameSiteFromBrowser(value string) domain.SameSite {
	switch strings.ToLower(value) {
	case "no_restriction", "none":
		return domain.SameSiteNone
	case "lax":
		return domain.SameSiteLax
	case "strict":
		return domain.SameSiteStrict
	default:
		return domain.SameSiteUnspecified
	}
}

// sameSiteToBrowser is the inverse of sameSiteFromBrowser.
func sameSiteToBrowser(value domain.SameSite) string {
	switch value {
	case domain.SameSiteNone:
		return "no_restriction"
	case domain.SameSiteLax:
		return "lax"
	case domain.SameSiteStrict:
		return "strict"
	default:
		return "unspecified"
	}
}

func orDefault(value, fallback string) string {
	if value == "" {
		return fallback
	}
	return value
}
