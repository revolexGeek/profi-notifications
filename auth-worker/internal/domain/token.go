package domain

import (
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"math"
	"sort"
	"strings"
)

const fingerprintLength = 12

// tokenCookieNames are the cookies whose value is a JWT carrying the session
// expiry. This is an enterprise rule about how profi.ru expresses auth state.
var tokenCookieNames = map[string]struct{}{
	"prfr_bo_tkn": {},
}

// authCookieNames are the cookies that together describe the authentication
// state. They are reported for diagnostics but only tokenCookieNames drive
// expiry decisions.
var authCookieNames = map[string]struct{}{
	"prfr_tkn":    {},
	"prfr_bo_tkn": {},
	"sid":         {},
	"sl-session":  {},
	"prfr_q_uuid": {},
	"prfr_q_val":  {},
	"uid":         {},
}

// IsTokenCookie reports whether the named cookie carries an auth JWT.
func IsTokenCookie(name string) bool {
	_, ok := tokenCookieNames[name]
	return ok
}

// IsAuthCookie reports whether the named cookie is part of the auth state.
func IsAuthCookie(name string) bool {
	_, ok := authCookieNames[name]
	return ok
}

// TokenInfo describes the freshest token cookie observed for a given name.
type TokenInfo struct {
	Name        string
	Expiration  int64
	Fingerprint string
	Cookie      Cookie
}

// TokenDetail is a serialisable snapshot of a single token cookie, used for
// status reporting. Nil pointers denote unavailable values.
type TokenDetail struct {
	Name          string
	Domain        string
	Path          string
	JWTExp        *int64
	JWTTTL        *int64
	CookieExpires *int64
	Fingerprint   string
}

// Fingerprint returns a short, stable, non-reversible identifier for a value,
// used to detect token changes without logging secrets.
func Fingerprint(value string) string {
	sum := sha256.Sum256([]byte(value))
	return hex.EncodeToString(sum[:])[:fingerprintLength]
}

// DecodeJWTExp extracts the "exp" claim from a JWT, returning the expiry as a
// unix timestamp. The boolean is false when the token is malformed or carries
// no expiry.
func DecodeJWTExp(token string) (int64, bool) {
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return 0, false
	}

	claims, ok := decodeJWTClaims(parts[1])
	if !ok || claims.Exp == nil {
		return 0, false
	}

	return int64(*claims.Exp), true
}

type jwtClaims struct {
	Exp *float64 `json:"exp"`
}

func decodeJWTClaims(segment string) (jwtClaims, bool) {
	if remainder := len(segment) % 4; remainder != 0 {
		segment += strings.Repeat("=", 4-remainder)
	}

	decoded, err := base64.URLEncoding.DecodeString(segment)
	if err != nil {
		return jwtClaims{}, false
	}

	var claims jwtClaims
	if err := json.Unmarshal(decoded, &claims); err != nil {
		return jwtClaims{}, false
	}

	return claims, true
}

// LatestTokens returns, per token cookie name, the copy with the furthest
// expiry. Cookies with unreadable tokens are ignored.
func (j *Jar) LatestTokens() map[string]TokenInfo {
	latest := make(map[string]TokenInfo)

	for _, cookie := range j.cookies {
		if !IsTokenCookie(cookie.Name) {
			continue
		}

		expiration, ok := DecodeJWTExp(cookie.Value)
		if !ok {
			continue
		}

		current, exists := latest[cookie.Name]
		if !exists || expiration > current.Expiration {
			latest[cookie.Name] = TokenInfo{
				Name:        cookie.Name,
				Expiration:  expiration,
				Fingerprint: Fingerprint(cookie.Value),
				Cookie:      cookie,
			}
		}
	}

	return latest
}

// TokenTTL returns the smallest remaining lifetime, in seconds, across the
// freshest token cookies. The boolean is false when no readable token exists.
func (j *Jar) TokenTTL(now int64) (int64, bool) {
	latest := j.LatestTokens()
	if len(latest) == 0 {
		return 0, false
	}

	shortest := int64(math.MaxInt64)
	for _, token := range latest {
		if remaining := token.Expiration - now; remaining < shortest {
			shortest = remaining
		}
	}

	return shortest, true
}

// TokenDetails returns a serialisable snapshot of every token cookie, sorted
// by location, for status reporting.
func (j *Jar) TokenDetails(now int64) []TokenDetail {
	var details []TokenDetail

	for _, cookie := range j.cookies {
		if !IsTokenCookie(cookie.Name) {
			continue
		}
		details = append(details, tokenDetail(cookie, now))
	}

	sort.Slice(details, func(a, b int) bool {
		return lessDetail(details[a], details[b])
	})

	return details
}

func tokenDetail(cookie Cookie, now int64) TokenDetail {
	detail := TokenDetail{
		Name:        cookie.Name,
		Domain:      cookie.Domain,
		Path:        cookie.Path,
		Fingerprint: Fingerprint(cookie.Value),
	}

	if expiration, ok := DecodeJWTExp(cookie.Value); ok {
		ttl := expiration - now
		detail.JWTExp = &expiration
		detail.JWTTTL = &ttl
	}

	if cookie.ExpiresAt != 0 {
		expires := cookie.ExpiresAt
		detail.CookieExpires = &expires
	}

	return detail
}

func lessDetail(a, b TokenDetail) bool {
	if a.Name != b.Name {
		return a.Name < b.Name
	}
	if a.Domain != b.Domain {
		return a.Domain < b.Domain
	}
	return a.Path < b.Path
}

// NeedsRefresh decides whether a renew is required: when no token exists or the
// shortest remaining lifetime is at or below the configured threshold.
func NeedsRefresh(ttl int64, hasTTL bool, thresholdSeconds int64) bool {
	return !hasTTL || ttl <= thresholdSeconds
}

// ChangedTokens returns the token names whose value or expiry differ between two
// snapshots. A token missing from the "after" snapshot is not considered
// changed, since it can no longer be evaluated.
func ChangedTokens(before, after map[string]TokenInfo) []string {
	var changed []string

	for name := range tokenCookieNames {
		next, present := after[name]
		if !present {
			continue
		}

		previous, existed := before[name]
		if !existed ||
			previous.Fingerprint != next.Fingerprint ||
			previous.Expiration != next.Expiration {
			changed = append(changed, name)
		}
	}

	sort.Strings(changed)
	return changed
}
