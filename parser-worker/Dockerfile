# syntax=docker/dockerfile:1

FROM rust:1.94.1-slim-bookworm AS builder

WORKDIR /build

COPY Cargo.toml Cargo.lock build.rs ./
COPY proto ./proto
COPY src ./src

# target is a cache mount (not kept in the layer), so install the binary out to
# a normal path. Cache ids are project-scoped to avoid clashes on a shared builder.
RUN --mount=type=cache,id=parser-worker-registry,target=/usr/local/cargo/registry,sharing=locked \
    --mount=type=cache,id=parser-worker-target,target=/build/target \
    cargo build --release --locked --bin parser-worker \
 && install -Dm0555 target/release/parser-worker /usr/local/bin/parser-worker

FROM debian:bookworm-slim AS runtime

# ca-certificates: reqwest uses rustls-native-certs, which reads the system trust store.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --gid 1001 app \
 && useradd --uid 1001 --gid 1001 --no-create-home app

COPY --from=builder /usr/local/bin/parser-worker /usr/local/bin/parser-worker

USER 1001:1001

ENTRYPOINT ["/usr/local/bin/parser-worker"]
