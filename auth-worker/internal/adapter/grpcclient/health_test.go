package grpcclient

import (
	"context"
	"net"
	"testing"
	"time"

	"google.golang.org/grpc"
	healthpb "google.golang.org/grpc/health/grpc_health_v1"
)

type stubHealth struct {
	healthpb.UnimplementedHealthServer
	status healthpb.HealthCheckResponse_ServingStatus
}

func (s stubHealth) Check(context.Context, *healthpb.HealthCheckRequest) (*healthpb.HealthCheckResponse, error) {
	return &healthpb.HealthCheckResponse{Status: s.status}, nil
}

func serveHealth(t *testing.T, status healthpb.HealthCheckResponse_ServingStatus) string {
	t.Helper()

	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}

	server := grpc.NewServer()
	healthpb.RegisterHealthServer(server, stubHealth{status: status})
	go func() { _ = server.Serve(listener) }()
	t.Cleanup(server.Stop)

	return listener.Addr().String()
}

func TestCheckHealthPassesWhenServing(t *testing.T) {
	target := serveHealth(t, healthpb.HealthCheckResponse_SERVING)

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	if err := CheckHealth(ctx, target); err != nil {
		t.Fatalf("ожидался успех, получено: %v", err)
	}
}

func TestCheckHealthFailsWhenNotServing(t *testing.T) {
	target := serveHealth(t, healthpb.HealthCheckResponse_NOT_SERVING)

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	if err := CheckHealth(ctx, target); err == nil {
		t.Fatal("ожидалась ошибка для NOT_SERVING")
	}
}

func TestCheckHealthFailsWhenUnreachable(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 1*time.Second)
	defer cancel()

	if err := CheckHealth(ctx, "127.0.0.1:1"); err == nil {
		t.Fatal("ожидалась ошибка при недоступном сервере")
	}
}
