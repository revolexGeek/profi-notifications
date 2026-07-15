package httprenew

import (
	"net/http"
	"sort"
	"strings"
	"time"

	"auth-worker/internal/domain"
)

const (
	defaultDomain = ".profi.ru"
	defaultPath   = "/"
)

// cookieHeader renders the jar's cookies as a single Cookie request header.
func cookieHeader(jar *domain.Jar) string {
	pairs := make([]string, 0, jar.Len())
	for _, cookie := range jar.Cookies() {
		pairs = append(pairs, cookie.Name+"="+cookie.Value)
	}
	return strings.Join(pairs, "; ")
}

// mergeResponseCookies folds the Set-Cookie cookies from a response into the
// jar and returns their names in sorted order.
func mergeResponseCookies(jar *domain.Jar, response *http.Response) []string {
	cookies := response.Cookies()

	unique := make(map[string]struct{}, len(cookies))
	for _, httpCookie := range cookies {
		jar.Set(domainCookie(httpCookie))
		unique[httpCookie.Name] = struct{}{}
	}

	names := make([]string, 0, len(unique))
	for name := range unique {
		names = append(names, name)
	}
	sort.Strings(names)
	return names
}

func domainCookie(httpCookie *http.Cookie) domain.Cookie {
	cookie := domain.Cookie{
		Name:     httpCookie.Name,
		Value:    httpCookie.Value,
		Domain:   orDefault(httpCookie.Domain, defaultDomain),
		Path:     orDefault(httpCookie.Path, defaultPath),
		Secure:   httpCookie.Secure,
		HTTPOnly: httpCookie.HttpOnly,
		SameSite: sameSiteFromHTTP(httpCookie.SameSite),
	}

	switch {
	case httpCookie.MaxAge > 0:
		cookie.ExpiresAt = time.Now().Unix() + int64(httpCookie.MaxAge)
	case !httpCookie.Expires.IsZero():
		cookie.ExpiresAt = httpCookie.Expires.Unix()
	default:
		cookie.Session = true
	}

	return cookie
}

func sameSiteFromHTTP(value http.SameSite) domain.SameSite {
	switch value {
	case http.SameSiteLaxMode:
		return domain.SameSiteLax
	case http.SameSiteStrictMode:
		return domain.SameSiteStrict
	case http.SameSiteNoneMode:
		return domain.SameSiteNone
	default:
		return domain.SameSiteUnspecified
	}
}

func orDefault(value, fallback string) string {
	if value == "" {
		return fallback
	}
	return value
}
