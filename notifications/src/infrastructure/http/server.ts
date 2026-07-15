import type { Logger } from '../../application/ports';

export interface HealthDeps {
  /** Liveness: is the process itself healthy? */
  readonly isLive: () => boolean;
  /** Readiness: is the service connected and consuming? */
  readonly isReady: () => boolean;
  /** Render the metrics body (Prometheus text format). */
  readonly renderMetrics: () => string;
}

/**
 * Pure request router (the testable core of the Humble Object). Handles
 * `/health` (liveness), `/ready` (readiness), and `/metrics`. Kept independent
 * of Bun.serve so it can be unit-tested with plain `Request` objects.
 */
export function createHealthRequestHandler(deps: HealthDeps): (req: Request) => Response {
  return (req: Request): Response => {
    if (req.method !== 'GET' && req.method !== 'HEAD') {
      return new Response('method not allowed', { status: 405 });
    }

    const { pathname } = new URL(req.url);
    switch (pathname) {
      case '/health':
      case '/healthz':
      case '/livez':
        return deps.isLive()
          ? Response.json({ status: 'ok' })
          : Response.json({ status: 'down' }, { status: 503 });

      case '/ready':
      case '/readyz':
        return deps.isReady()
          ? Response.json({ status: 'ready' })
          : Response.json({ status: 'not-ready' }, { status: 503 });

      case '/metrics':
        return new Response(deps.renderMetrics(), {
          status: 200,
          headers: { 'content-type': 'text/plain; version=0.0.4; charset=utf-8' },
        });

      default:
        return new Response('not found', { status: 404 });
    }
  };
}

export interface HttpServerOptions extends HealthDeps {
  readonly host: string;
  readonly port: number;
  readonly logger: Logger;
}

/** Binds the health router to a Bun.serve instance (the humble wrapper). */
export function startHealthServer(options: HttpServerOptions): ReturnType<typeof Bun.serve> {
  const handler = createHealthRequestHandler(options);
  const server = Bun.serve({
    hostname: options.host,
    port: options.port,
    fetch: handler,
  });
  options.logger.info('http server listening', { host: options.host, port: server.port });
  return server;
}
