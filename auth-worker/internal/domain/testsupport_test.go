package domain

import (
	"encoding/base64"
	"fmt"
)

// makeJWT builds an unsigned JWT whose payload carries the given exp claim and
// the "touched" status, encoded without padding like a real token.
func makeJWT(exp int64) string {
	return makeJWTStatus(exp, TokenStatusTouched)
}

// makeJWTStatus builds an unsigned JWT with the given exp and status claims.
func makeJWTStatus(exp int64, status string) string {
	header := base64.RawURLEncoding.EncodeToString([]byte(`{"alg":"HS256","typ":"JWT"}`))
	payload := base64.RawURLEncoding.EncodeToString([]byte(fmt.Sprintf(`{"exp":%d,"status":%q}`, exp, status)))
	return header + "." + payload + ".signature"
}

// tokenCookie builds a touched prfr_bo_tkn cookie whose JWT expires at exp.
func tokenCookie(path string, exp int64) Cookie {
	return Cookie{
		Name:      "prfr_bo_tkn",
		Value:     makeJWT(exp),
		Domain:    ".profi.ru",
		Path:      path,
		ExpiresAt: exp + 1000,
	}
}
