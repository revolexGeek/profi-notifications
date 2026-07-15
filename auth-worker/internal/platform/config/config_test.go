package config

import (
	"testing"
	"time"
)

func TestLoadAppliesOverrides(t *testing.T) {
	t.Setenv("PROFI_COOKIE_JSON", "/tmp/cookies.json")
	t.Setenv("PROFI_CHECK_INTERVAL", "15")
	t.Setenv("PROFI_REFRESH_BEFORE", "90")
	t.Setenv("PROFI_REQUEST_TIMEOUT", "2.5")
	t.Setenv("PROFI_RUN_ONCE", "1")
	t.Setenv("PROFI_USER_AGENT", "test-agent")

	cfg := Load()

	if cfg.CookieFile != "/tmp/cookies.json" {
		t.Errorf("cookie file = %q", cfg.CookieFile)
	}
	if cfg.CheckInterval != 15*time.Second {
		t.Errorf("check interval = %s, want 15s", cfg.CheckInterval)
	}
	if cfg.RefreshBeforeSeconds != 90 {
		t.Errorf("refresh before = %d, want 90", cfg.RefreshBeforeSeconds)
	}
	if cfg.RequestTimeout != 2500*time.Millisecond {
		t.Errorf("request timeout = %s, want 2.5s", cfg.RequestTimeout)
	}
	if !cfg.RunOnce {
		t.Error("run once should be true when PROFI_RUN_ONCE=1")
	}
	if cfg.Headers()["user-agent"] != "test-agent" {
		t.Errorf("user-agent header = %q, want test-agent", cfg.Headers()["user-agent"])
	}
}

func TestLoadFallsBackToDefaults(t *testing.T) {
	for _, key := range []string{"PROFI_COOKIE_JSON", "PROFI_CHECK_INTERVAL", "PROFI_REFRESH_BEFORE", "PROFI_RUN_ONCE"} {
		t.Setenv(key, "")
		if err := unset(key); err != nil {
			t.Fatalf("unset %s: %v", key, err)
		}
	}

	cfg := Load()

	if cfg.CookieFile != "./data/cookies.json" {
		t.Errorf("cookie file = %q, want default", cfg.CookieFile)
	}
	if cfg.CheckInterval != 60*time.Second {
		t.Errorf("check interval = %s, want default 60s", cfg.CheckInterval)
	}
	if cfg.RefreshBeforeSeconds != 180 {
		t.Errorf("refresh before = %d, want default 180", cfg.RefreshBeforeSeconds)
	}
	if cfg.RunOnce {
		t.Error("run once should default to false")
	}
}

func TestLoadIgnoresInvalidNumbers(t *testing.T) {
	t.Setenv("PROFI_CHECK_INTERVAL", "not-a-number")
	t.Setenv("PROFI_REQUEST_TIMEOUT", "bogus")

	cfg := Load()

	if cfg.CheckInterval != 60*time.Second {
		t.Errorf("check interval = %s, want default 60s on invalid input", cfg.CheckInterval)
	}
	if cfg.RequestTimeout != 30*time.Second {
		t.Errorf("request timeout = %s, want default 30s on invalid input", cfg.RequestTimeout)
	}
}
