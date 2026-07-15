/**
 * Minimal, dependency-free metrics registry that renders the Prometheus text
 * exposition format. Kept deliberately small — the service exposes a handful of
 * counters via the `/metrics` endpoint.
 */

/** Output port used by the messaging adapter to record processing outcomes. */
export interface Metrics {
  recordReceived(): void;
  recordDelivered(): void;
  recordRetried(): void;
  recordDeadLettered(category: string): void;
}

export interface MetricsSnapshot {
  readonly received: number;
  readonly delivered: number;
  readonly retried: number;
  readonly deadLettered: Readonly<Record<string, number>>;
}

export class MetricsRegistry implements Metrics {
  private received = 0;
  private delivered = 0;
  private retried = 0;
  private readonly deadLettered = new Map<string, number>();

  recordReceived(): void {
    this.received += 1;
  }

  recordDelivered(): void {
    this.delivered += 1;
  }

  recordRetried(): void {
    this.retried += 1;
  }

  recordDeadLettered(category: string): void {
    this.deadLettered.set(category, (this.deadLettered.get(category) ?? 0) + 1);
  }

  snapshot(): MetricsSnapshot {
    return {
      received: this.received,
      delivered: this.delivered,
      retried: this.retried,
      deadLettered: Object.fromEntries(this.deadLettered),
    };
  }

  /** Render all metrics in the Prometheus text exposition format. */
  render(): string {
    const lines: string[] = [];

    pushCounter(lines, 'notifications_received_total', 'Messages received from the broker.', [
      { value: this.received },
    ]);
    pushCounter(
      lines,
      'notifications_delivered_total',
      'Messages successfully delivered to Telegram.',
      [{ value: this.delivered }],
    );
    pushCounter(lines, 'notifications_retried_total', 'Messages routed to the retry queue.', [
      { value: this.retried },
    ]);
    pushCounter(
      lines,
      'notifications_dead_lettered_total',
      'Messages routed to the dead-letter queue, by reason.',
      [...this.deadLettered.entries()].map(([category, value]) => ({
        value,
        labels: { category },
      })),
    );

    return lines.join('\n') + '\n';
  }
}

interface Sample {
  readonly value: number;
  readonly labels?: Readonly<Record<string, string>>;
}

function pushCounter(lines: string[], name: string, help: string, samples: Sample[]): void {
  lines.push(`# HELP ${name} ${help}`);
  lines.push(`# TYPE ${name} counter`);
  for (const sample of samples) {
    lines.push(`${name}${formatLabels(sample.labels)} ${sample.value}`);
  }
}

function formatLabels(labels?: Readonly<Record<string, string>>): string {
  if (!labels) return '';
  const entries = Object.entries(labels);
  if (entries.length === 0) return '';
  const inner = entries.map(([key, value]) => `${key}="${escapeLabelValue(value)}"`).join(',');
  return `{${inner}}`;
}

function escapeLabelValue(value: string): string {
  return value.replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\n/g, '\\n');
}
