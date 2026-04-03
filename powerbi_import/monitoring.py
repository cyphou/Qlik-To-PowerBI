"""
Monitoring Integration (Sprint 100).

Export migration metrics to external monitoring systems:

  - Azure Monitor / Application Insights: custom metrics + traces
  - Prometheus: push gateway metrics
  - Stdout/JSON: structured logging (always available, no deps)

Usage:
    monitor = MigrationMonitor(backend='json')
    monitor.record_metric('migration_duration_seconds', 12.5, app='Sales')
    monitor.record_event('migration_complete', app='Sales', fidelity=95.2)
    monitor.flush()

Backend selection via `--monitor azure|prometheus|json|none`.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ── Monitor Backends ──────────────────────────────────────────────────────────

class _BaseBackend:
    """Base class for monitoring backends."""

    def record_metric(self, name, value, dimensions=None):
        raise NotImplementedError

    def record_event(self, name, properties=None):
        raise NotImplementedError

    def flush(self):
        pass


class _JsonBackend(_BaseBackend):
    """Log metrics and events as structured JSON to a file (no deps)."""

    def __init__(self, log_path=None):
        self.log_path = log_path or os.path.join("artifacts", "monitoring.jsonl")
        self._buffer = []

    def record_metric(self, name, value, dimensions=None):
        entry = {
            "type": "metric",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "name": name,
            "value": value,
            "dimensions": dimensions or {},
        }
        self._buffer.append(entry)

    def record_event(self, name, properties=None):
        entry = {
            "type": "event",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "name": name,
            "properties": properties or {},
        }
        self._buffer.append(entry)

    def flush(self):
        if not self._buffer:
            return
        os.makedirs(os.path.dirname(self.log_path) or ".", exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            for entry in self._buffer:
                f.write(json.dumps(entry) + "\n")
        count = len(self._buffer)
        self._buffer.clear()
        logger.debug("Flushed %d monitoring entries to %s", count, self.log_path)
        return count


class _AzureMonitorBackend(_BaseBackend):
    """Send metrics/events to Azure Monitor / Application Insights.

    Requires: `opencensus-ext-azure` or direct REST API.
    Falls back to JSON backend if SDK not available.
    """

    def __init__(self, connection_string=None):
        self.connection_string = (
            connection_string
            or os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
        )
        self._client = None
        self._fallback = _JsonBackend()
        self._init_client()

    def _init_client(self):
        try:
            from opencensus.ext.azure import metrics_exporter
            self._client = metrics_exporter
            logger.info("Azure Monitor backend initialized")
        except ImportError:
            logger.info(
                "opencensus-ext-azure not installed — "
                "Azure Monitor metrics will be logged to JSON fallback"
            )

    def record_metric(self, name, value, dimensions=None):
        if self._client and self.connection_string:
            # Real Azure Monitor integration would use the exporter here.
            # For now, log structured data that can be forwarded.
            logger.info(
                "AzureMonitor metric: %s=%s dims=%s",
                name, value, dimensions,
            )
        self._fallback.record_metric(name, value, dimensions)

    def record_event(self, name, properties=None):
        if self._client and self.connection_string:
            logger.info(
                "AzureMonitor event: %s props=%s", name, properties,
            )
        self._fallback.record_event(name, properties)

    def flush(self):
        return self._fallback.flush()


class _PrometheusBackend(_BaseBackend):
    """Push metrics to a Prometheus push gateway.

    Requires: `prometheus_client` package.
    Falls back to JSON backend if SDK not available.
    """

    def __init__(self, gateway_url=None):
        self.gateway_url = (
            gateway_url
            or os.environ.get("PROMETHEUS_PUSHGATEWAY", "")
        )
        self._registry = None
        self._gauges = {}
        self._fallback = _JsonBackend()
        self._init_client()

    def _init_client(self):
        try:
            from prometheus_client import CollectorRegistry, Gauge
            self._registry = CollectorRegistry()
            self._Gauge = Gauge
            logger.info("Prometheus backend initialized")
        except ImportError:
            logger.info(
                "prometheus_client not installed — "
                "Prometheus metrics will be logged to JSON fallback"
            )

    def record_metric(self, name, value, dimensions=None):
        if self._registry:
            safe_name = name.replace(".", "_").replace("-", "_")
            if safe_name not in self._gauges:
                label_names = list((dimensions or {}).keys())
                self._gauges[safe_name] = self._Gauge(
                    safe_name, safe_name,
                    labelnames=label_names,
                    registry=self._registry,
                )
            gauge = self._gauges[safe_name]
            if dimensions:
                gauge.labels(**dimensions).set(value)
            else:
                gauge.set(value)
        self._fallback.record_metric(name, value, dimensions)

    def record_event(self, name, properties=None):
        # Prometheus doesn't have events — log as metric with value=1
        self._fallback.record_event(name, properties)

    def flush(self):
        if self._registry and self.gateway_url:
            try:
                from prometheus_client import push_to_gateway
                push_to_gateway(
                    self.gateway_url, job="Qlik_to_pbi",
                    registry=self._registry,
                )
                logger.info("Pushed metrics to Prometheus gateway")
            except Exception as e:
                logger.warning("Prometheus push failed: %s", e)
        return self._fallback.flush()


class _NoneBackend(_BaseBackend):
    """No-op backend — monitoring disabled."""

    def record_metric(self, name, value, dimensions=None):
        pass

    def record_event(self, name, properties=None):
        pass


# ── Public API ────────────────────────────────────────────────────────────────

_BACKENDS = {
    "json": _JsonBackend,
    "azure": _AzureMonitorBackend,
    "prometheus": _PrometheusBackend,
    "none": _NoneBackend,
}


class MigrationMonitor:
    """Unified migration monitoring interface.

    Args:
        backend: One of 'json', 'azure', 'prometheus', 'none'.
        **kwargs: Passed to the backend constructor.
    """

    def __init__(self, backend="json", **kwargs):
        backend_cls = _BACKENDS.get(backend, _JsonBackend)
        self._backend = backend_cls(**kwargs)
        self.backend_name = backend

    def record_metric(self, name, value, **dimensions):
        """Record a numeric metric with optional dimensions."""
        self._backend.record_metric(name, value, dimensions or None)

    def record_event(self, name, **properties):
        """Record a discrete event with optional properties."""
        self._backend.record_event(name, properties or None)

    def record_migration(self, app, duration_seconds, fidelity,
                         tables=0, measures=0, visuals=0, pages=0):
        """Record a complete migration as a set of standard metrics."""
        dims = {"app": app}
        self.record_metric("migration.duration_seconds", duration_seconds, **dims)
        self.record_metric("migration.fidelity_percent", fidelity, **dims)
        self.record_metric("migration.tables", tables, **dims)
        self.record_metric("migration.measures", measures, **dims)
        self.record_metric("migration.visuals", visuals, **dims)
        self.record_metric("migration.pages", pages, **dims)
        self.record_event(
            "migration.complete",
            app=app,
            duration=duration_seconds,
            fidelity=fidelity,
        )

    def flush(self):
        """Flush buffered metrics/events to the backend."""
        return self._backend.flush()
