package main

import "testing"

func TestHealthTargetNormalizesWildcardHost(t *testing.T) {
	cases := map[string]string{
		"0.0.0.0:50051":   "127.0.0.1:50051",
		"[::]:50051":      "127.0.0.1:50051",
		"127.0.0.1:50051": "127.0.0.1:50051",
		"localhost:9000":  "localhost:9000",
		"garbage":         "garbage",
	}

	for input, want := range cases {
		if got := healthTarget(input); got != want {
			t.Errorf("healthTarget(%q) = %q, want %q", input, got, want)
		}
	}
}
