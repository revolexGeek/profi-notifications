package grpcserver

import (
	"context"
	"errors"
	"testing"

	healthpb "google.golang.org/grpc/health/grpc_health_v1"

	"auth-worker/internal/domain"
	"auth-worker/internal/usecase"
)

func healthStatus(t *testing.T, provider fakeProvider) healthpb.HealthCheckResponse_ServingStatus {
	t.Helper()
	resp, err := NewHealth(provider, discardLogger()).Check(context.Background(), &healthpb.HealthCheckRequest{})
	if err != nil {
		t.Fatalf("неожиданная ошибка: %v", err)
	}
	return resp.GetStatus()
}

func TestHealthServingWhenCookiesOk(t *testing.T) {
	provider := fakeProvider{snapshot: usecase.CookieSnapshot{Status: domain.StatusOK, HasToken: true, TokenTTL: 600}}

	if got := healthStatus(t, provider); got != healthpb.HealthCheckResponse_SERVING {
		t.Errorf("status = %s, want SERVING", got)
	}
}

func TestHealthNotServingWhenRequiresLogin(t *testing.T) {
	provider := fakeProvider{snapshot: usecase.CookieSnapshot{Status: domain.StatusRequiresLogin}}

	if got := healthStatus(t, provider); got != healthpb.HealthCheckResponse_NOT_SERVING {
		t.Errorf("status = %s, want NOT_SERVING", got)
	}
}

func TestHealthNotServingWhenProviderFails(t *testing.T) {
	provider := fakeProvider{err: errors.New("нет cookies")}

	if got := healthStatus(t, provider); got != healthpb.HealthCheckResponse_NOT_SERVING {
		t.Errorf("status = %s, want NOT_SERVING", got)
	}
}
