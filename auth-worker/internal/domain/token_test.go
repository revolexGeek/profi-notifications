package domain

import (
	"encoding/base64"
	"testing"
)

func TestDecodeJWTExpReadsExpiry(t *testing.T) {
	exp, ok := DecodeJWTExp(makeJWT(1_700_000_000))

	if !ok {
		t.Fatal("expected a readable expiry")
	}
	if exp != 1_700_000_000 {
		t.Fatalf("exp = %d, want 1700000000", exp)
	}
}

func TestDecodeJWTExpRejectsMalformedTokens(t *testing.T) {
	noExpPayload := base64.RawURLEncoding.EncodeToString([]byte(`{"sub":"user"}`))

	cases := map[string]string{
		"two segments":      "header.payload",
		"four segments":     "a.b.c.d",
		"invalid base64":    "eyJ.!!!not-base64!!!.sig",
		"invalid json":      "eyJ." + base64.RawURLEncoding.EncodeToString([]byte("not json")) + ".sig",
		"missing exp claim": "eyJ." + noExpPayload + ".sig",
	}

	for name, token := range cases {
		t.Run(name, func(t *testing.T) {
			if _, ok := DecodeJWTExp(token); ok {
				t.Errorf("expected token %q to be rejected", token)
			}
		})
	}
}

func TestFingerprintIsStableAndShort(t *testing.T) {
	first := Fingerprint("some-token-value")
	second := Fingerprint("some-token-value")

	if first != second {
		t.Fatalf("fingerprint not stable: %q != %q", first, second)
	}
	if len(first) != fingerprintLength {
		t.Fatalf("fingerprint length = %d, want %d", len(first), fingerprintLength)
	}
	if Fingerprint("other-value") == first {
		t.Fatal("different values produced the same fingerprint")
	}
}

func TestJarTokenTTLReturnsFreshestLifetime(t *testing.T) {
	const now = int64(1_000_000)
	jar := NewJar([]Cookie{
		tokenCookie("/old", now+100),
		tokenCookie("/new", now+500),
		{Name: "sid", Value: "ignored", Domain: ".profi.ru", Path: "/"},
	})

	ttl, ok := jar.TokenTTL(now)

	if !ok {
		t.Fatal("expected a TTL")
	}
	if ttl != 500 {
		t.Fatalf("ttl = %d, want 500 (freshest token wins)", ttl)
	}
}

func TestJarTokenTTLAbsentWithoutTokens(t *testing.T) {
	jar := NewJar([]Cookie{{Name: "sid", Value: "x", Domain: ".profi.ru", Path: "/"}})

	if _, ok := jar.TokenTTL(0); ok {
		t.Fatal("expected no TTL when no token cookies exist")
	}
}

func TestRemoveOldTokenDuplicatesKeepsFreshest(t *testing.T) {
	const now = int64(1_000_000)
	jar := NewJar([]Cookie{
		tokenCookie("/old", now+100),
		tokenCookie("/new", now+500),
	})

	removed := jar.RemoveOldTokenDuplicates()

	if len(removed) != 1 {
		t.Fatalf("removed %d cookies, want 1", len(removed))
	}
	if removed[0].Path != "/old" {
		t.Fatalf("removed path = %q, want /old", removed[0].Path)
	}
	if jar.Len() != 1 {
		t.Fatalf("jar length = %d, want 1", jar.Len())
	}
}

func TestChangedTokensDetectsNewValue(t *testing.T) {
	before := map[string]TokenInfo{
		"prfr_bo_tkn": {Name: "prfr_bo_tkn", Expiration: 100, Fingerprint: "aaa"},
	}
	after := map[string]TokenInfo{
		"prfr_bo_tkn": {Name: "prfr_bo_tkn", Expiration: 200, Fingerprint: "bbb"},
	}

	changed := ChangedTokens(before, after)

	if len(changed) != 1 || changed[0] != "prfr_bo_tkn" {
		t.Fatalf("changed = %v, want [prfr_bo_tkn]", changed)
	}
}

func TestChangedTokensIgnoresUnchanged(t *testing.T) {
	snapshot := map[string]TokenInfo{
		"prfr_bo_tkn": {Name: "prfr_bo_tkn", Expiration: 100, Fingerprint: "aaa"},
	}

	if changed := ChangedTokens(snapshot, snapshot); len(changed) != 0 {
		t.Fatalf("changed = %v, want empty", changed)
	}
}

func TestNeedsRefresh(t *testing.T) {
	const threshold = int64(180)

	cases := []struct {
		name   string
		ttl    int64
		hasTTL bool
		want   bool
	}{
		{"no token", 0, false, true},
		{"below threshold", 100, true, true},
		{"at threshold", 180, true, true},
		{"above threshold", 500, true, false},
		{"already expired", -10, true, true},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := NeedsRefresh(tc.ttl, tc.hasTTL, threshold); got != tc.want {
				t.Errorf("NeedsRefresh(%d, %t) = %t, want %t", tc.ttl, tc.hasTTL, got, tc.want)
			}
		})
	}
}

func TestTokenDetailsPopulatesExpiry(t *testing.T) {
	const now = int64(1_000_000)
	jar := NewJar([]Cookie{tokenCookie("/", now+300)})

	details := jar.TokenDetails(now)

	if len(details) != 1 {
		t.Fatalf("details count = %d, want 1", len(details))
	}
	detail := details[0]
	if detail.JWTExp == nil || *detail.JWTExp != now+300 {
		t.Fatalf("jwt exp = %v, want %d", detail.JWTExp, now+300)
	}
	if detail.JWTTTL == nil || *detail.JWTTTL != 300 {
		t.Fatalf("jwt ttl = %v, want 300", detail.JWTTTL)
	}
	if detail.CookieExpires == nil {
		t.Fatal("cookie expires should be set")
	}
}

func TestTokenStatusReadsClaim(t *testing.T) {
	status, ok := TokenStatus(makeJWTStatus(1_700_000_000, "renew"))
	if !ok || status != "renew" {
		t.Fatalf("status = %q ok = %t, want renew/true", status, ok)
	}
}

func TestAllTouched(t *testing.T) {
	const now = int64(1_000_000)

	touched := NewJar([]Cookie{tokenCookie("/", now+500)})
	if !touched.AllTouched() {
		t.Error("jar with a touched token should report AllTouched")
	}

	renew := NewJar([]Cookie{{
		Name: "prfr_bo_tkn", Domain: ".profi.ru", Path: "/",
		Value: makeJWTStatus(now+500, "renew"),
	}})
	if renew.AllTouched() {
		t.Error("jar with a renew-status token must not report AllTouched")
	}

	empty := NewJar([]Cookie{{Name: "sid", Value: "x", Domain: ".profi.ru", Path: "/"}})
	if empty.AllTouched() {
		t.Error("jar without token cookies must not report AllTouched")
	}
}
