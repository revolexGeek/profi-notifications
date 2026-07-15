// Package grpcserver exposes the cookie use case over gRPC. It is a delivery
// mechanism at the edge of the system: it translates gRPC calls into use case
// invocations and use case results (and errors) into protobuf responses and
// gRPC status codes.
package grpcserver

import (
	"context"
	"errors"
	"log/slog"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"auth-worker/internal/domain"
	authv1 "auth-worker/internal/gen/auth/v1"
	"auth-worker/internal/usecase"
)

// CookieProvider is the inbound port the server depends on. *usecase.GetCookies
// satisfies it; the interface keeps the server testable in isolation.
type CookieProvider interface {
	Execute() (usecase.CookieSnapshot, error)
}

// Server implements the generated CookieServiceServer.
type Server struct {
	authv1.UnimplementedCookieServiceServer
	cookies CookieProvider
	log     *slog.Logger
}

// New creates a Server backed by the given cookie provider.
func New(cookies CookieProvider, log *slog.Logger) *Server {
	return &Server{cookies: cookies, log: log}
}

// Register attaches the service to a gRPC server (or any registrar).
func (s *Server) Register(registrar grpc.ServiceRegistrar) {
	authv1.RegisterCookieServiceServer(registrar, s)
}

// GetCookies returns the current cookie snapshot.
func (s *Server) GetCookies(_ context.Context, _ *authv1.GetCookiesRequest) (*authv1.GetCookiesResponse, error) {
	snapshot, err := s.cookies.Execute()
	if err != nil {
		return nil, s.toStatusError(err)
	}

	s.log.Info("served cookies", "status", snapshot.Status, "count", len(snapshot.Cookies), "has_token", snapshot.HasToken)
	return toResponse(snapshot), nil
}

// toStatusError maps a use case error to an appropriate gRPC status. A missing
// or invalid cookie file is a precondition the caller can act on; anything else
// is internal and its detail is not leaked.
func (s *Server) toStatusError(err error) error {
	var cookieFile *domain.CookieFileError
	if errors.As(err, &cookieFile) {
		return status.Error(codes.FailedPrecondition, err.Error())
	}

	s.log.Error("get cookies failed", "error", err)
	return status.Error(codes.Internal, "could not read cookies")
}
