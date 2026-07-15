package grpcserver

import (
	"context"
	"log/slog"

	"google.golang.org/grpc"
	healthpb "google.golang.org/grpc/health/grpc_health_v1"

	"auth-worker/internal/domain"
)

// HealthServer implements the standard grpc.health.v1 service. Health reflects
// real readiness: the service is SERVING only when it can currently hand out a
// live, usable cookie set.
type HealthServer struct {
	healthpb.UnimplementedHealthServer
	cookies CookieProvider
	log     *slog.Logger
}

// NewHealth creates a HealthServer backed by the cookie provider.
func NewHealth(cookies CookieProvider, log *slog.Logger) *HealthServer {
	return &HealthServer{cookies: cookies, log: log}
}

// Register attaches the health service to a gRPC server.
func (h *HealthServer) Register(registrar grpc.ServiceRegistrar) {
	healthpb.RegisterHealthServer(registrar, h)
}

// Check reports SERVING when a live token is available, otherwise NOT_SERVING.
func (h *HealthServer) Check(_ context.Context, _ *healthpb.HealthCheckRequest) (*healthpb.HealthCheckResponse, error) {
	return &healthpb.HealthCheckResponse{Status: h.servingStatus()}, nil
}

func (h *HealthServer) servingStatus() healthpb.HealthCheckResponse_ServingStatus {
	snapshot, err := h.cookies.Execute()
	if err != nil {
		h.log.Warn("проверка здоровья: не удалось прочитать cookies", "error", err)
		return healthpb.HealthCheckResponse_NOT_SERVING
	}

	if snapshot.Status != domain.StatusOK {
		return healthpb.HealthCheckResponse_NOT_SERVING
	}

	return healthpb.HealthCheckResponse_SERVING
}
