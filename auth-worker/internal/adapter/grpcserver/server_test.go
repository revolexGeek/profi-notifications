package grpcserver

import (
	"context"
	"errors"
	"io"
	"log/slog"
	"net"
	"testing"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
	"google.golang.org/grpc/test/bufconn"

	"auth-worker/internal/domain"
	authv1 "auth-worker/internal/gen/auth/v1"
	"auth-worker/internal/usecase"
)

type fakeProvider struct {
	snapshot usecase.CookieSnapshot
	err      error
}

func (f fakeProvider) Execute() (usecase.CookieSnapshot, error) {
	return f.snapshot, f.err
}

func discardLogger() *slog.Logger {
	return slog.New(slog.NewTextHandler(io.Discard, nil))
}

func dialFake(t *testing.T, provider CookieProvider) authv1.CookieServiceClient {
	t.Helper()

	listener := bufconn.Listen(1024 * 1024)
	server := grpc.NewServer()
	New(provider, discardLogger()).Register(server)

	go func() { _ = server.Serve(listener) }()
	t.Cleanup(server.Stop)

	conn, err := grpc.NewClient(
		"passthrough:///bufnet",
		grpc.WithContextDialer(func(ctx context.Context, _ string) (net.Conn, error) {
			return listener.DialContext(ctx)
		}),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		t.Fatalf("dial: %v", err)
	}
	t.Cleanup(func() { _ = conn.Close() })

	return authv1.NewCookieServiceClient(conn)
}

func TestGetCookiesReturnsMappedSnapshot(t *testing.T) {
	provider := fakeProvider{snapshot: usecase.CookieSnapshot{
		Cookies: []domain.Cookie{{
			Name:      "prfr_bo_tkn",
			Value:     "token",
			Domain:    ".profi.ru",
			Path:      "/",
			Secure:    true,
			HTTPOnly:  true,
			SameSite:  domain.SameSiteNone,
			ExpiresAt: 1784230477,
		}},
		CookieHeader: "prfr_bo_tkn=token",
		Status:       domain.StatusOK,
		TokenTTL:     600,
		HasToken:     true,
	}}
	client := dialFake(t, provider)

	resp, err := client.GetCookies(context.Background(), &authv1.GetCookiesRequest{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if resp.GetStatus() != "ok" {
		t.Errorf("status = %q, want ok", resp.GetStatus())
	}
	if resp.GetTokenTtl() != 600 || !resp.GetHasToken() {
		t.Errorf("token ttl = %d has = %t, want 600/true", resp.GetTokenTtl(), resp.GetHasToken())
	}
	if resp.GetCookieHeader() != "prfr_bo_tkn=token" {
		t.Errorf("cookie header = %q", resp.GetCookieHeader())
	}
	if len(resp.GetCookies()) != 1 {
		t.Fatalf("cookie count = %d, want 1", len(resp.GetCookies()))
	}
	cookie := resp.GetCookies()[0]
	if cookie.GetName() != "prfr_bo_tkn" || cookie.GetSameSite() != "None" || !cookie.GetHttpOnly() {
		t.Errorf("cookie mapped incorrectly: %+v", cookie)
	}
}

func TestGetCookiesMapsCookieFileErrorToFailedPrecondition(t *testing.T) {
	client := dialFake(t, fakeProvider{err: &domain.CookieFileError{Message: "cookie file not found"}})

	_, err := client.GetCookies(context.Background(), &authv1.GetCookiesRequest{})

	if code := status.Code(err); code != codes.FailedPrecondition {
		t.Fatalf("code = %s, want FailedPrecondition", code)
	}
}

func TestGetCookiesMapsUnknownErrorToInternal(t *testing.T) {
	client := dialFake(t, fakeProvider{err: errors.New("disk on fire")})

	_, err := client.GetCookies(context.Background(), &authv1.GetCookiesRequest{})

	if code := status.Code(err); code != codes.Internal {
		t.Fatalf("code = %s, want Internal", code)
	}
}
