"""Тесты метрик планировщика (Prometheus-текст)."""

from app.infrastructure.observability.metrics import PrometheusMetrics


def test_counts_published_commands() -> None:
    metrics = PrometheusMetrics()

    metrics.command_published()
    metrics.command_published()

    assert "scheduler_commands_published_total 2" in metrics.render()


def test_render_is_prometheus_text() -> None:
    text = PrometheusMetrics().render()

    assert "# TYPE scheduler_commands_published_total counter" in text
    assert "scheduler_last_command_timestamp_seconds" in text
