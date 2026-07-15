// Command auth-worker keeps profi.ru authentication cookies fresh and serves the
// current cookies over gRPC. This file is the composition root: the only place
// that knows every concrete type. It reads configuration, wires the adapters
// into the use cases, starts the gRPC server, and drives the refresh loop.
package main

import (
	"context"
	"log/slog"
	"net"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"google.golang.org/grpc"

	"auth-worker/internal/adapter/cookiefile"
	"auth-worker/internal/adapter/filelock"
	"auth-worker/internal/adapter/grpcserver"
	"auth-worker/internal/adapter/httprenew"
	"auth-worker/internal/adapter/statusfile"
	"auth-worker/internal/platform/clock"
	"auth-worker/internal/platform/config"
	"auth-worker/internal/usecase"
)

func main() {
	cfg := config.Load()
	logger := newLogger(cfg.LogLevel)

	systemClock := clock.System{}
	store := cookiefile.New(cfg.CookieFile)
	locker := filelock.New(cfg.LockFile, cfg.LockTimeout)

	worker := buildWorker(cfg, logger, store, locker, systemClock)
	getCookies := usecase.NewGetCookies(store, locker, systemClock)

	logStartup(logger, cfg)

	if cfg.RunOnce {
		worker.RunOnce()
		logger.Info("PROFI_RUN_ONCE=1, exiting")
		return
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	grpcServer, err := serveGRPC(cfg.GRPCAddr, getCookies, logger)
	if err != nil {
		logger.Error("failed to start gRPC server", "error", err)
		os.Exit(1)
	}
	defer grpcServer.GracefulStop()

	runLoop(ctx, worker, logger)
}

func buildWorker(
	cfg config.Config,
	logger *slog.Logger,
	store *cookiefile.Store,
	locker *filelock.Locker,
	systemClock clock.System,
) *usecase.Worker {
	renewer := httprenew.New(cfg.RenewURL, cfg.Headers(), cfg.RequestTimeout, logger)
	reporter := statusfile.New(cfg.StatusFile)

	refresh := usecase.NewRefreshAuth(store, renewer, locker, systemClock, logger, cfg.RefreshBeforeSeconds)

	return usecase.NewWorker(refresh, reporter, systemClock, logger, usecase.Intervals{
		Check:       cfg.CheckInterval,
		AuthExpired: cfg.AuthExpiredInterval,
		Error:       cfg.ErrorInterval,
	})
}

func serveGRPC(addr string, getCookies grpcserver.CookieProvider, logger *slog.Logger) (*grpc.Server, error) {
	listener, err := net.Listen("tcp", addr)
	if err != nil {
		return nil, err
	}

	server := grpc.NewServer()
	grpcserver.New(getCookies, logger).Register(server)

	go func() {
		if serveErr := server.Serve(listener); serveErr != nil {
			logger.Error("gRPC server stopped", "error", serveErr)
		}
	}()

	logger.Info("gRPC server listening", "addr", addr)
	return server, nil
}

func runLoop(ctx context.Context, worker *usecase.Worker, logger *slog.Logger) {
	for {
		sleep := worker.RunOnce()
		logger.Info("scheduling next check", "in", sleep)

		select {
		case <-ctx.Done():
			logger.Info("shutdown signal received, stopping")
			return
		case <-time.After(sleep):
		}
	}
}

func logStartup(logger *slog.Logger, cfg config.Config) {
	logger.Info("auth-worker started",
		"cookie_file", cfg.CookieFile,
		"status_file", cfg.StatusFile,
		"grpc_addr", cfg.GRPCAddr,
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
