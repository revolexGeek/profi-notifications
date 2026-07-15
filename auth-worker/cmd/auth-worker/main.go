// Command auth-worker keeps profi.ru authentication cookies fresh. This file is
// the composition root: the only place that knows every concrete type. It reads
// configuration, wires the adapters into the use cases, and drives the loop.
package main

import (
	"log/slog"
	"os"
	"strings"
	"time"

	"auth-worker/internal/adapter/cookiefile"
	"auth-worker/internal/adapter/filelock"
	"auth-worker/internal/adapter/httprenew"
	"auth-worker/internal/adapter/statusfile"
	"auth-worker/internal/platform/clock"
	"auth-worker/internal/platform/config"
	"auth-worker/internal/usecase"
)

func main() {
	cfg := config.Load()
	logger := newLogger(cfg.LogLevel)
	worker := buildWorker(cfg, logger)

	logStartup(logger, cfg)
	run(worker, cfg, logger)
}

func buildWorker(cfg config.Config, logger *slog.Logger) *usecase.Worker {
	systemClock := clock.System{}

	store := cookiefile.New(cfg.CookieFile)
	renewer := httprenew.New(cfg.RenewURL, cfg.Headers(), cfg.RequestTimeout, logger)
	locker := filelock.New(cfg.LockFile, cfg.LockTimeout)
	reporter := statusfile.New(cfg.StatusFile)

	refresh := usecase.NewRefreshAuth(store, renewer, locker, systemClock, logger, cfg.RefreshBeforeSeconds)

	return usecase.NewWorker(refresh, reporter, systemClock, logger, usecase.Intervals{
		Check:       cfg.CheckInterval,
		AuthExpired: cfg.AuthExpiredInterval,
		Error:       cfg.ErrorInterval,
	})
}

func run(worker *usecase.Worker, cfg config.Config, logger *slog.Logger) {
	for {
		sleep := worker.RunOnce()

		if cfg.RunOnce {
			logger.Info("PROFI_RUN_ONCE=1, exiting")
			return
		}

		logger.Info("scheduling next check", "in", sleep)
		time.Sleep(sleep)
	}
}

func logStartup(logger *slog.Logger, cfg config.Config) {
	logger.Info("auth-worker started",
		"cookie_file", cfg.CookieFile,
		"status_file", cfg.StatusFile,
		"check_interval", cfg.CheckInterval,
	)
}

func newLogger(level string) *slog.Logger {
	handler := slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: parseLevel(level)})
	return slog.New(handler)
}

func parseLevel(level string) slog.Level {
	switch strings.ToUpper(strings.TrimSpace(level)) {
	case "DEBUG":
		return slog.LevelDebug
	case "WARN", "WARNING":
		return slog.LevelWarn
	case "ERROR":
		return slog.LevelError
	default:
		return slog.LevelInfo
	}
}
