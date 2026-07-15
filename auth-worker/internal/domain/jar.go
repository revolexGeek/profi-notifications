package domain

import "sort"

// Jar is an ordered collection of cookies with browser-like identity semantics:
// setting a cookie replaces any existing cookie sharing its (name, domain, path)
// identity, otherwise it is appended.
type Jar struct {
	cookies []Cookie
}

// NewJar builds a jar from the given cookies, applying identity-based
// deduplication in insertion order.
func NewJar(cookies []Cookie) *Jar {
	jar := &Jar{}
	for _, cookie := range cookies {
		jar.Set(cookie)
	}
	return jar
}

// Set inserts a cookie, replacing any existing cookie with the same identity.
func (j *Jar) Set(cookie Cookie) {
	for index := range j.cookies {
		if j.cookies[index].SameIdentity(cookie) {
			j.cookies[index] = cookie
			return
		}
	}
	j.cookies = append(j.cookies, cookie)
}

// Cookies returns the cookies currently held by the jar.
func (j *Jar) Cookies() []Cookie {
	return j.cookies
}

// Len reports how many cookies the jar holds.
func (j *Jar) Len() int {
	return len(j.cookies)
}

// RemoveOldTokenDuplicates drops every token cookie that is not the freshest
// copy for its name, returning the cookies that were removed.
func (j *Jar) RemoveOldTokenDuplicates() []Cookie {
	latest := j.LatestTokens()

	kept := make([]Cookie, 0, len(j.cookies))
	var removed []Cookie

	for _, cookie := range j.cookies {
		if isStaleDuplicate(cookie, latest) {
			removed = append(removed, cookie)
			continue
		}
		kept = append(kept, cookie)
	}

	j.cookies = kept
	return removed
}

func isStaleDuplicate(cookie Cookie, latest map[string]TokenInfo) bool {
	if !IsTokenCookie(cookie.Name) {
		return false
	}
	newest, exists := latest[cookie.Name]
	if !exists {
		return false
	}
	return !newest.Cookie.SameValue(cookie)
}

// authCookiesSorted returns the auth-relevant cookies in a stable order, for
// deterministic logging.
func (j *Jar) authCookiesSorted() []Cookie {
	var auth []Cookie
	for _, cookie := range j.cookies {
		if IsAuthCookie(cookie.Name) {
			auth = append(auth, cookie)
		}
	}
	sort.Slice(auth, func(a, b int) bool {
		return lessByLocation(auth[a], auth[b])
	})
	return auth
}

// AuthCookies returns the cookies used to describe the authentication state,
// in a stable order suitable for logging or diagnostics.
func (j *Jar) AuthCookies() []Cookie {
	return j.authCookiesSorted()
}

func lessByLocation(a, b Cookie) bool {
	if a.Name != b.Name {
		return a.Name < b.Name
	}
	if a.Domain != b.Domain {
		return a.Domain < b.Domain
	}
	return a.Path < b.Path
}
