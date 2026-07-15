import { describe, expect, it } from 'bun:test';
import { MetricsRegistry } from './metrics';

describe('MetricsRegistry', () => {
  it('starts at zero for all counters', () => {
    const metrics = new MetricsRegistry();

    expect(metrics.snapshot()).toEqual({
      received: 0,
      delivered: 0,
      retried: 0,
      deadLettered: {},
    });
  });

  it('counts each recorded outcome', () => {
    const metrics = new MetricsRegistry();

    metrics.recordReceived();
    metrics.recordReceived();
    metrics.recordDelivered();
    metrics.recordRetried();
    metrics.recordDeadLettered('permanent');
    metrics.recordDeadLettered('permanent');
    metrics.recordDeadLettered('exhausted');

    expect(metrics.snapshot()).toEqual({
      received: 2,
      delivered: 1,
      retried: 1,
      deadLettered: { permanent: 2, exhausted: 1 },
    });
  });

  it('renders counters in Prometheus text format', () => {
    const metrics = new MetricsRegistry();
    metrics.recordReceived();
    metrics.recordDelivered();

    const output = metrics.render();

    expect(output).toContain('# TYPE notifications_received_total counter');
    expect(output).toContain('notifications_received_total 1');
    expect(output).toContain('notifications_delivered_total 1');
    expect(output).toContain('notifications_retried_total 0');
    expect(output.endsWith('\n')).toBe(true);
  });

  it('renders dead-letter counters with a category label', () => {
    const metrics = new MetricsRegistry();
    metrics.recordDeadLettered('validation');

    const output = metrics.render();

    expect(output).toContain('notifications_dead_lettered_total{category="validation"} 1');
  });

  it('escapes special characters in label values', () => {
    const metrics = new MetricsRegistry();
    metrics.recordDeadLettered('weird"value');

    const output = metrics.render();

    expect(output).toContain('category="weird\\"value"');
  });
});
