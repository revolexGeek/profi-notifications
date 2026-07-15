package grpcserver

import (
	"auth-worker/internal/domain"
	authv1 "auth-worker/internal/gen/auth/v1"
	"auth-worker/internal/usecase"
)

func toResponse(snapshot usecase.CookieSnapshot) *authv1.GetCookiesResponse {
	return &authv1.GetCookiesResponse{
		Cookies:      toProtoCookies(snapshot.Cookies),
		CookieHeader: snapshot.CookieHeader,
		Status:       string(snapshot.Status),
		TokenTtl:     snapshot.TokenTTL,
		HasToken:     snapshot.HasToken,
	}
}

func toProtoCookies(cookies []domain.Cookie) []*authv1.Cookie {
	proto := make([]*authv1.Cookie, 0, len(cookies))
	for _, cookie := range cookies {
		proto = append(proto, toProtoCookie(cookie))
	}
	return proto
}

func toProtoCookie(cookie domain.Cookie) *authv1.Cookie {
	return &authv1.Cookie{
		Name:      cookie.Name,
		Value:     cookie.Value,
		Domain:    cookie.Domain,
		Path:      cookie.Path,
		Secure:    cookie.Secure,
		HttpOnly:  cookie.HTTPOnly,
		HostOnly:  cookie.HostOnly,
		Session:   cookie.Session,
		SameSite:  string(cookie.SameSite),
		ExpiresAt: cookie.ExpiresAt,
	}
}
