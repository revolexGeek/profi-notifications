# syntax=docker/dockerfile:1

FROM golang:1.26.5-alpine AS builder

WORKDIR /src
ENV CGO_ENABLED=0 \
    GOOS=linux \
    GOTOOLCHAIN=local

COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod \
    go mod download

COPY . .
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    go build -trimpath -buildvcs=false -ldflags="-s -w" \
    -o /out/auth-worker ./cmd/auth-worker
RUN mkdir -p /out/data

FROM gcr.io/distroless/static-debian12:nonroot AS runtime

WORKDIR /app
COPY --from=builder /out/auth-worker /app/auth-worker
COPY --from=builder --chown=nonroot:nonroot /out/data /app/data

ENV PROFI_GRPC_ADDR=0.0.0.0:50051

EXPOSE 50051
USER nonroot:nonroot

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["/app/auth-worker", "healthcheck"]

ENTRYPOINT ["/app/auth-worker"]
