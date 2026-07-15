import { afterAll, beforeAll, describe, expect, it } from 'bun:test';
import { createSilentLogger } from '../../../tests/support/fakes';
import { createHealthRequestHandler, startHealthServer, type HealthDeps } from './server';

function handlerWith(overrides: Partial<HealthDeps> = {}) {
  return createHealthRequestHandler({
    isLive: () => true,
    isReady: () => true,
    renderMetrics: () => 'metric 1\n',
    ...overrides,
  });
}

describe('createHealthRequestHandler', () => {
  it('returns 200 ok on /health when live', async () => {
    const res = handlerWith()(new Request('http://x/health'));

    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ status: 'ok' });
  });

  it('returns 503 on /health when not live', () => {
    const res = handlerWith({ isLive: () => false })(new Request('http://x/health'));

    expect(res.status).toBe(503);
  });

  it('returns 200 on /ready when ready', () => {
    const res = handlerWith()(new Request('http://x/ready'));

    expect(res.status).toBe(200);
  });

  it('returns 503 on /ready when not ready', async () => {
    const res = handlerWith({ isReady: () => false })(new Request('http://x/ready'));

    expect(res.status).toBe(503);
    expect(await res.json()).toEqual({ status: 'not-ready' });
  });

  it('serves metrics as plain text', async () => {
    const res = handlerWith({ renderMetrics: () => 'my_metric 42\n' })(
      new Request('http://x/metrics'),
    );

    expect(res.status).toBe(200);
    expect(res.headers.get('content-type')).toContain('text/plain');
    expect(await res.text()).toBe('my_metric 42\n');
  });

  it('returns 404 for unknown paths', () => {
    expect(handlerWith()(new Request('http://x/nope')).status).toBe(404);
  });

  it('returns 405 for non-GET methods', () => {
    const res = handlerWith()(new Request('http://x/health', { method: 'POST' }));

    expect(res.status).toBe(405);
  });
});

describe('startHealthServer (bound)', () => {
  let ready = false;
  let server: ReturnType<typeof startHealthServer>;

  beforeAll(() => {
    server = startHealthServer({
      host: '127.0.0.1',
      port: 0,
      logger: createSilentLogger(),
      isLive: () => true,
      isReady: () => ready,
      renderMetrics: () => 'served_metric 1\n',
    });
  });

  afterAll(async () => {
    await server.stop(true);
  });

  it('answers /health over HTTP', async () => {
    const res = await fetch(`http://127.0.0.1:${server.port}/health`);

    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ status: 'ok' });
  });

  it('reflects readiness changes on /ready', async () => {
    ready = false;
    const down = await fetch(`http://127.0.0.1:${server.port}/ready`);
    expect(down.status).toBe(503);

    ready = true;
    const up = await fetch(`http://127.0.0.1:${server.port}/ready`);
    expect(up.status).toBe(200);
  });

  it('serves /metrics over HTTP', async () => {
    const res = await fetch(`http://127.0.0.1:${server.port}/metrics`);

    expect(await res.text()).toBe('served_metric 1\n');
  });
});
