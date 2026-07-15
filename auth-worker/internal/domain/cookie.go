// Package domain holds the enterprise business rules of the auth-worker:
// the entities and pure logic that would exist regardless of how cookies are
// stored, how sessions are renewed, or how the process is scheduled. Nothing
// in this package imports a framework, a transport, or a persistence detail.
package domain

// SameSite is the canonical SameSite policy of a cookie. It is carried through
// the system purely to round-trip cookies faithfully; the domain never
// interprets it.
type SameSite string

const (
	SameSiteUnspecified SameSite = "unspecified"
	SameSiteNone        SameSite = "None"
	SameSiteLax         SameSite = "Lax"
	SameSiteStrict      SameSite = "Strict"
)

// Cookie is a single browser cookie participating in profi.ru authentication.
type Cookie struct {
	Name     string
	Value    string
	Domain   string
	Path     string
	Secure   bool
	HTTPOnly bool
	HostOnly bool
	Session  bool
	SameSite SameSite
	// ExpiresAt is the cookie's own expiry as a unix timestamp in seconds.
	// Zero means the cookie has no persistent expiry.
	ExpiresAt int64
}

// IsSession reports whether the cookie should be treated as a session cookie,
// i.e. it declares itself session-scoped or carries no persistent expiry.
func (c Cookie) IsSession() bool {
	return c.Session || c.ExpiresAt == 0
}

// SameIdentity reports whether two cookies address the same slot, identified by
// the (name, domain, path) triple browsers use to deduplicate.
func (c Cookie) SameIdentity(other Cookie) bool {
	return c.Name == other.Name &&
		c.Domain == other.Domain &&
		c.Path == other.Path
}

// SameValue reports whether two cookies share identity and value, i.e. they are
// indistinguishable copies.
func (c Cookie) SameValue(other Cookie) bool {
	return c.SameIdentity(other) && c.Value == other.Value
}
