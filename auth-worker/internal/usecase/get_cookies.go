package usecase

import (
	"strings"

	"auth-worker/internal/domain"
)

// CookieSnapshot is the client-facing view of the current cookie jar: the
// structured cookies, a ready-to-use HTTP Cookie header, and the auth state.
type CookieSnapshot struct {
	Cookies      []domain.Cookie
	CookieHeader string
	Status       domain.Status
	TokenTTL     int64
	HasToken     bool
}

// GetCookies reads the current cookies and derives a snapshot other services
// can use to make authenticated requests. It never renews; it only reports the
// state maintained by the refresh loop.
type GetCookies struct {
	store  CookieStore
	locker Locker
	clock  Clock
}

// NewGetCookies wires the interactor with its collaborators.
func NewGetCookies(store CookieStore, locker Locker, clock Clock) *GetCookies {
	return &GetCookies{store: store, locker: locker, clock: clock}
}

// Execute loads the cookies under the lock and builds a snapshot.
func (uc *GetCookies) Execute() (CookieSnapshot, error) {
	release, err := uc.locker.Acquire()
	if err != nil {
		return CookieSnapshot{}, err
	}
	defer func() { _ = release() }()

	jar, _, err := uc.store.Load()
	if err != nil {
		return CookieSnapshot{}, err
	}

	ttl, hasToken := jar.TokenTTL(uc.clock.Now())

	return CookieSnapshot{
		Cookies:      jar.Cookies(),
		CookieHeader: cookieHeader(jar.Cookies()),
		Status:       snapshotStatus(ttl, hasToken),
		TokenTTL:     ttl,
		HasToken:     hasToken,
	}, nil
}

func snapshotStatus(ttl int64, hasToken bool) domain.Status {
	if hasToken && ttl > 0 {
		return domain.StatusOK
	}
	return domain.StatusRequiresLogin
}

// cookieHeader renders cookies as an HTTP "Cookie" header value.
func cookieHeader(cookies []domain.Cookie) string {
	pairs := make([]string, 0, len(cookies))
	for _, cookie := range cookies {
		pairs = append(pairs, cookie.Name+"="+cookie.Value)
	}
	return strings.Join(pairs, "; ")
}
