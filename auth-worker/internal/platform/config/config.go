// Package config reads the worker configuration from the environment, applying
// the same variables and defaults as the original Python worker. It is a
// framework-layer detail: the inner layers receive plain values, never env
// lookups.
package config

import (
	"os"
	"strconv"
	"time"
)

// Config is the fully resolved worker configuration.
type Config struct {
	CookieFile string
	LockFile   string
	StatusFile string

	RenewURL  string
	TouchURL  string
	UserAgent string
	LogLevel  string
	GRPCAddr  string

	RefreshBeforeSeconds int64

	CheckInterval       time.Duration
	AuthExpiredInterval time.Duration
	ErrorInterval       time.Duration
	RequestTimeout      time.Duration
	LockTimeout         time.Duration

	RunOnce bool
}

const defaultUserAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) " +
	"AppleWebKit/537.36 (KHTML, like Gecko) " +
	"Chrome/150.0.0.0 Safari/537.36"

// Load resolves the configuration from the environment.
func Load() Config {
	return Config{
		CookieFile: env("PROFI_COOKIE_JSON", "./data/cookies.json"),
		LockFile:   env("PROFI_COOKIE_LOCK", "./data/cookies.lock"),
		StatusFile: env("PROFI_AUTH_STATUS", "./data/auth-status.json"),

		RenewURL:  env("PROFI_RENEW_URL", "https://profi.ru/auth/token/renew"),
		TouchURL:  env("PROFI_TOUCH_URL", "https://profi.ru/auth/token/touch"),
		UserAgent: env("PROFI_USER_AGENT", defaultUserAgent),
		LogLevel:  env("LOG_LEVEL", "INFO"),
		GRPCAddr:  env("PROFI_GRPC_ADDR", "127.0.0.1:50051"),

		RefreshBeforeSeconds: envInt("PROFI_REFRESH_BEFORE", 180),

		CheckInterval:       envSeconds("PROFI_CHECK_INTERVAL", 60),
		AuthExpiredInterval: envSeconds("PROFI_AUTH_EXPIRED_INTERVAL", 300),
		ErrorInterval:       envSeconds("PROFI_ERROR_INTERVAL", 60),
		RequestTimeout:      envFractionalSeconds("PROFI_REQUEST_TIMEOUT", 30),
		LockTimeout:         envFractionalSeconds("PROFI_LOCK_TIMEOUT", 30),

		RunOnce: env("PROFI_RUN_ONCE", "0") == "1",
	}
}

// Headers returns the common request headers, injecting the configured
// user agent.
func (c Config) Headers() map[string]string {
	return map[string]string{
		"accept":                "*/*",
		"accept-language":       "ru,en-US;q=0.9,en;q=0.8",
		"referer":               "https://profi.ru/backoffice/n.php",
		"user-agent":            c.UserAgent,
		"x-app-id":              "BO",
		"x-new-auth-compatible": "1",
		"x-requested-with":      "XMLHttpRequest",
		"x-warp-ui-app":         "WEBBO",
		"x-warp-ui-type":        "WEB",
		"x-warp-ui-ver":         "1.0",
	}
}

func env(key, fallback string) string {
	if value, ok := os.LookupEnv(key); ok {
		return value
	}
	return fallback
}

func envInt(key string, fallback int64) int64 {
	value, ok := os.LookupEnv(key)
	if !ok {
		return fallback
	}
	parsed, err := strconv.ParseInt(value, 10, 64)
	if err != nil {
		return fallback
	}
	return parsed
}

func envSeconds(key string, fallbackSeconds int64) time.Duration {
	return time.Duration(envInt(key, fallbackSeconds)) * time.Second
}

func envFractionalSeconds(key string, fallbackSeconds float64) time.Duration {
	value, ok := os.LookupEnv(key)
	if !ok {
		return secondsToDuration(fallbackSeconds)
	}
	parsed, err := strconv.ParseFloat(value, 64)
	if err != nil {
		return secondsToDuration(fallbackSeconds)
	}
	return secondsToDuration(parsed)
}

func secondsToDuration(seconds float64) time.Duration {
	return time.Duration(seconds * float64(time.Second))
}
