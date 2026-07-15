package domain

import "testing"

func TestCookieIsSession(t *testing.T) {
	cases := []struct {
		name   string
		cookie Cookie
		want   bool
	}{
		{"declared session", Cookie{Session: true, ExpiresAt: 123}, true},
		{"no expiry", Cookie{Session: false, ExpiresAt: 0}, true},
		{"persistent", Cookie{Session: false, ExpiresAt: 123}, false},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := tc.cookie.IsSession(); got != tc.want {
				t.Errorf("IsSession() = %t, want %t", got, tc.want)
			}
		})
	}
}

func TestCookieSameIdentityIgnoresValue(t *testing.T) {
	base := Cookie{Name: "prfr_bo_tkn", Domain: ".profi.ru", Path: "/", Value: "one"}
	sameSlot := Cookie{Name: "prfr_bo_tkn", Domain: ".profi.ru", Path: "/", Value: "two"}
	otherPath := Cookie{Name: "prfr_bo_tkn", Domain: ".profi.ru", Path: "/bo", Value: "one"}

	if !base.SameIdentity(sameSlot) {
		t.Error("cookies with same name/domain/path should share identity")
	}
	if base.SameIdentity(otherPath) {
		t.Error("different path should not share identity")
	}
	if base.SameValue(sameSlot) {
		t.Error("different value should not be equal")
	}
	if !base.SameValue(base) {
		t.Error("identical cookie should be equal to itself")
	}
}

func TestJarSetReplacesSameIdentity(t *testing.T) {
	jar := NewJar([]Cookie{{Name: "a", Domain: ".profi.ru", Path: "/", Value: "old"}})

	jar.Set(Cookie{Name: "a", Domain: ".profi.ru", Path: "/", Value: "new"})

	if jar.Len() != 1 {
		t.Fatalf("jar length = %d, want 1 (replacement, not append)", jar.Len())
	}
	if jar.Cookies()[0].Value != "new" {
		t.Fatalf("value = %q, want new", jar.Cookies()[0].Value)
	}
}

func TestJarSetAppendsNewIdentity(t *testing.T) {
	jar := NewJar([]Cookie{{Name: "a", Domain: ".profi.ru", Path: "/", Value: "v"}})

	jar.Set(Cookie{Name: "b", Domain: ".profi.ru", Path: "/", Value: "v"})

	if jar.Len() != 2 {
		t.Fatalf("jar length = %d, want 2", jar.Len())
	}
}

func TestJarAuthCookiesFiltersAndSorts(t *testing.T) {
	jar := NewJar([]Cookie{
		{Name: "uid", Domain: ".profi.ru", Path: "/", Value: "u"},
		{Name: "not_auth", Domain: ".profi.ru", Path: "/", Value: "x"},
		{Name: "sid", Domain: ".profi.ru", Path: "/", Value: "s"},
	})

	auth := jar.AuthCookies()

	if len(auth) != 2 {
		t.Fatalf("auth cookie count = %d, want 2", len(auth))
	}
	if auth[0].Name != "sid" || auth[1].Name != "uid" {
		t.Fatalf("auth cookies not sorted by name: %q, %q", auth[0].Name, auth[1].Name)
	}
}
