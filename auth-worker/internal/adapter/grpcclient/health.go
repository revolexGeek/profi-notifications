// Package grpcclient holds thin gRPC client helpers used by the CLI, such as the
// self-contained health probe invoked by the container health check.
package grpcclient

import (
	"context"
	"fmt"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	healthpb "google.golang.org/grpc/health/grpc_health_v1"
)

// CheckHealth dials target and queries the grpc.health.v1 service, returning nil
// only when the server reports SERVING.
func CheckHealth(ctx context.Context, target string) error {
	conn, err := grpc.NewClient(target, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return fmt.Errorf("не удалось подключиться к %s: %w", target, err)
	}
	defer conn.Close()

	resp, err := healthpb.NewHealthClient(conn).Check(ctx, &healthpb.HealthCheckRequest{})
	if err != nil {
		return fmt.Errorf("health-запрос не выполнен: %w", err)
	}

	if resp.GetStatus() != healthpb.HealthCheckResponse_SERVING {
		return fmt.Errorf("сервис не готов: %s", resp.GetStatus())
	}

	return nil
}
