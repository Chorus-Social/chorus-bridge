# Chorus Bridge - Monitoring Guide

## 📊 **Monitoring Overview**

This guide covers comprehensive monitoring setup for the Chorus Bridge, including metrics collection, logging, alerting, and observability best practices.

## 🏗️ **Monitoring Architecture**

### **Observability Stack**

```
┌─────────────────────────────────────────────────────────────┐
│                    Monitoring Stack                        │
├─────────────────────────────────────────────────────────────┤
│  Application: Chorus Bridge (Metrics + Logs)              │
├─────────────────────────────────────────────────────────────┤
│  Collection: Prometheus (Metrics) + Fluentd (Logs)        │
├─────────────────────────────────────────────────────────────┤
│  Storage: Prometheus TSDB + Elasticsearch (Logs)          │
├─────────────────────────────────────────────────────────────┤
│  Visualization: Grafana (Dashboards + Alerts)            │
├─────────────────────────────────────────────────────────────┤
│  Alerting: Alertmanager + PagerDuty/Slack                 │
└─────────────────────────────────────────────────────────────┘
```

### **Monitoring Components**

1. **Metrics Collection** - Prometheus for time-series data
2. **Log Aggregation** - Centralized logging with structured logs
3. **Visualization** - Grafana dashboards and charts
4. **Alerting** - Automated alerts for critical issues
5. **Tracing** - Distributed tracing for request flows

## 📈 **Metrics Collection**

### **Application Metrics**

The Chorus Bridge exposes comprehensive metrics via Prometheus:

```python
# Metrics definitions
from prometheus_client import Counter, Histogram, Gauge, Summary

# Request metrics
bridge_events_received_total = Counter(
    'bridge_events_received_total',
    'Total number of federation events received'
)

bridge_events_processed_total = Counter(
    'bridge_events_processed_total',
    'Total number of federation events processed',
    ['message_type', 'status']
)

bridge_events_failed_total = Counter(
    'bridge_events_failed_total',
    'Total number of failed federation events',
    ['error_type', 'stage_instance']
)

# Performance metrics
bridge_request_duration_seconds = Histogram(
    'bridge_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'endpoint', 'status_code']
)

bridge_request_size_bytes = Histogram(
    'bridge_request_size_bytes',
    'Request size in bytes',
    ['method', 'endpoint']
)

# Conductor metrics
bridge_conductor_requests_total = Counter(
    'bridge_conductor_requests_total',
    'Total number of requests to conductor',
    ['method', 'status', 'endpoint']
)

bridge_conductor_latency_seconds = Histogram(
    'bridge_conductor_latency_seconds',
    'Latency of conductor requests',
    ['method', 'endpoint']
)

bridge_conductor_cache_hits_total = Counter(
    'bridge_conductor_cache_hits_total',
    'Total number of cache hits for conductor requests',
    ['cache_type', 'operation']
)

# Circuit breaker metrics
bridge_conductor_circuit_breaker_state = Gauge(
    'bridge_conductor_circuit_breaker_state',
    'Circuit breaker state (0=CLOSED, 1=OPEN, 2=HALF_OPEN)',
    ['client_type', 'endpoint']
)

# Connection pool metrics
bridge_conductor_connection_pool_size = Gauge(
    'bridge_conductor_connection_pool_size',
    'Number of connections in the conductor pool',
    ['pool_type', 'state']
)

# Business metrics
bridge_peer_count = Gauge(
    'bridge_peer_count',
    'Number of connected peers'
)

bridge_blacklist_size = Gauge(
    'bridge_blacklist_size',
    'Number of blacklisted instances'
)

bridge_trust_store_size = Gauge(
    'bridge_trust_store_size',
    'Number of instances in trust store'
)

# System metrics
bridge_memory_usage_bytes = Gauge(
    'bridge_memory_usage_bytes',
    'Memory usage in bytes'
)

bridge_cpu_usage_percent = Gauge(
    'bridge_cpu_usage_percent',
    'CPU usage percentage'
)
```

### **Database Metrics**

```python
# Database performance metrics
bridge_database_connections_active = Gauge(
    'bridge_database_connections_active',
    'Number of active database connections'
)

bridge_database_connections_idle = Gauge(
    'bridge_database_connections_idle',
    'Number of idle database connections'
)

bridge_database_query_duration_seconds = Histogram(
    'bridge_database_query_duration_seconds',
    'Database query duration in seconds',
    ['operation', 'table']
)

bridge_database_errors_total = Counter(
    'bridge_database_errors_total',
    'Total number of database errors',
    ['error_type', 'operation']
)
```

### **Custom Metrics**

```python
# Custom business metrics
class BridgeMetrics:
    def __init__(self):
        self.federation_messages_by_type = Counter(
            'bridge_federation_messages_by_type_total',
            'Federation messages by type',
            ['message_type', 'source_instance']
        )
        
        self.activitypub_exports_total = Counter(
            'bridge_activitypub_exports_total',
            'Total ActivityPub exports',
            ['status', 'target_instance']
        )
        
        self.moderation_events_total = Counter(
            'bridge_moderation_events_total',
            'Total moderation events',
            ['action', 'target_type']
        )
    
    def record_federation_message(self, message_type: str, source_instance: str):
        """Record federation message metrics."""
        self.federation_messages_by_type.labels(
            message_type=message_type,
            source_instance=source_instance
        ).inc()
    
    def record_activitypub_export(self, status: str, target_instance: str):
        """Record ActivityPub export metrics."""
        self.activitypub_exports_total.labels(
            status=status,
            target_instance=target_instance
        ).inc()
```

## 📝 **Logging Configuration**

### **Structured Logging**

```python
# Logging configuration
import logging
import json
from datetime import datetime

class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logs."""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add extra fields if present
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        return json.dumps(log_entry)

# Configure logging
def setup_logging(log_level: str = "INFO"):
    """Setup structured logging."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )
    
    # Set formatter for all handlers
    for handler in logging.root.handlers:
        handler.setFormatter(StructuredFormatter())
```

### **Log Levels and Categories**

```python
# Logging categories
class LogCategories:
    # Application logs
    APPLICATION = "application"
    SECURITY = "security"
    PERFORMANCE = "performance"
    BUSINESS = "business"
    
    # System logs
    SYSTEM = "system"
    DATABASE = "database"
    NETWORK = "network"
    CONDUCTOR = "conductor"

# Logging utilities
def log_security_event(event_type: str, details: dict):
    """Log security-related events."""
    logger = logging.getLogger('security')
    logger.info(
        f"Security event: {event_type}",
        extra={
            'category': LogCategories.SECURITY,
            'event_type': event_type,
            'details': details
        }
    )

def log_performance_metric(metric_name: str, value: float, unit: str = "seconds"):
    """Log performance metrics."""
    logger = logging.getLogger('performance')
    logger.info(
        f"Performance metric: {metric_name}",
        extra={
            'category': LogCategories.PERFORMANCE,
            'metric_name': metric_name,
            'value': value,
            'unit': unit
        }
    )
```

## 📊 **Grafana Dashboards**

### **Main Dashboard**

```json
{
  "dashboard": {
    "title": "Chorus Bridge - Main Dashboard",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(bridge_events_received_total[5m])",
            "legendFormat": "Events/sec"
          }
        ],
        "yAxes": [
          {
            "label": "Requests/sec"
          }
        ]
      },
      {
        "title": "Error Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(bridge_events_failed_total[5m])",
            "legendFormat": "Errors/sec"
          }
        ],
        "yAxes": [
          {
            "label": "Errors/sec"
          }
        ]
      },
      {
        "title": "Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(bridge_request_duration_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          },
          {
            "expr": "histogram_quantile(0.50, rate(bridge_request_duration_seconds_bucket[5m]))",
            "legendFormat": "50th percentile"
          }
        ],
        "yAxes": [
          {
            "label": "Seconds"
          }
        ]
      },
      {
        "title": "Conductor Health",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(bridge_conductor_requests_total[5m])",
            "legendFormat": "Requests/sec"
          },
          {
            "expr": "histogram_quantile(0.95, rate(bridge_conductor_latency_seconds_bucket[5m]))",
            "legendFormat": "95th percentile latency"
          }
        ]
      },
      {
        "title": "Circuit Breaker Status",
        "type": "graph",
        "targets": [
          {
            "expr": "bridge_conductor_circuit_breaker_state",
            "legendFormat": "{{client_type}} - {{endpoint}}"
          }
        ]
      },
      {
        "title": "Database Connections",
        "type": "graph",
        "targets": [
          {
            "expr": "bridge_database_connections_active",
            "legendFormat": "Active connections"
          },
          {
            "expr": "bridge_database_connections_idle",
            "legendFormat": "Idle connections"
          }
        ]
      }
    ]
  }
}
```

### **Security Dashboard**

```json
{
  "dashboard": {
    "title": "Chorus Bridge - Security Dashboard",
    "panels": [
      {
        "title": "Authentication Failures",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(bridge_auth_failures_total[5m])",
            "legendFormat": "Auth failures/sec"
          }
        ]
      },
      {
        "title": "Rate Limit Violations",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(bridge_rate_limit_violations_total[5m])",
            "legendFormat": "Rate limit violations/sec"
          }
        ]
      },
      {
        "title": "Signature Verification Failures",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(bridge_signature_failures_total[5m])",
            "legendFormat": "Signature failures/sec"
          }
        ]
      },
      {
        "title": "Blacklist Size",
        "type": "graph",
        "targets": [
          {
            "expr": "bridge_blacklist_size",
            "legendFormat": "Blacklisted instances"
          }
        ]
      },
      {
        "title": "Trust Store Size",
        "type": "graph",
        "targets": [
          {
            "expr": "bridge_trust_store_size",
            "legendFormat": "Trusted instances"
          }
        ]
      }
    ]
  }
}
```

## 🚨 **Alerting Configuration**

### **Alert Rules**

```yaml
# monitoring/rules/bridge.yml
groups:
- name: chorus-bridge
  rules:
  # High error rate
  - alert: HighErrorRate
    expr: rate(bridge_events_failed_total[5m]) > 0.1
    for: 2m
    labels:
      severity: warning
    annotations:
      summary: "High error rate detected"
      description: "Error rate is {{ $value }} errors/sec"
  
  # High latency
  - alert: HighLatency
    expr: histogram_quantile(0.95, rate(bridge_request_duration_seconds_bucket[5m])) > 1
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High latency detected"
      description: "95th percentile latency is {{ $value }}s"
  
  # Service down
  - alert: ServiceDown
    expr: up{job="chorus-bridge"} == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Chorus Bridge service is down"
      description: "The Chorus Bridge service has been down for more than 1 minute"
  
  # Database connection issues
  - alert: DatabaseConnectionIssues
    expr: bridge_database_connections_active == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Database connection issues"
      description: "No active database connections"
  
  # Conductor communication issues
  - alert: ConductorCommunicationIssues
    expr: rate(bridge_conductor_requests_total{status="error"}[5m]) > 0.1
    for: 2m
    labels:
      severity: warning
    annotations:
      summary: "Conductor communication issues"
      description: "High rate of conductor request failures"
  
  # Circuit breaker open
  - alert: CircuitBreakerOpen
    expr: bridge_conductor_circuit_breaker_state == 1
    for: 1m
    labels:
      severity: warning
    annotations:
      summary: "Circuit breaker is open"
      description: "Conductor circuit breaker is open for {{ $labels.client_type }}"
  
  # High memory usage
  - alert: HighMemoryUsage
    expr: bridge_memory_usage_bytes / 1024 / 1024 / 1024 > 1
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High memory usage"
      description: "Memory usage is {{ $value }}GB"
  
  # Security events
  - alert: SecurityEvent
    expr: rate(bridge_auth_failures_total[5m]) > 10
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "High authentication failure rate"
      description: "Authentication failure rate is {{ $value }} failures/sec"
```

### **Alertmanager Configuration**

```yaml
# monitoring/alertmanager.yml
global:
  smtp_smarthost: 'localhost:587'
  smtp_from: 'alerts@chorus.network'

route:
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'web.hook'

receivers:
- name: 'web.hook'
  webhook_configs:
  - url: 'http://localhost:5001/'
    send_resolved: true

- name: 'slack'
  slack_configs:
  - api_url: 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK'
    channel: '#alerts'
    title: 'Chorus Bridge Alert'
    text: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'

- name: 'pagerduty'
  pagerduty_configs:
  - service_key: 'YOUR_PAGERDUTY_SERVICE_KEY'
    description: '{{ .GroupLabels.alertname }}'
```

## 🔍 **Tracing Configuration**

### **Distributed Tracing**

```python
# Tracing configuration
from opentelemetry import trace
from opentelemetry.exporter.jaeger import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

def setup_tracing():
    """Setup distributed tracing."""
    # Create tracer provider
    trace.set_tracer_provider(TracerProvider())
    tracer = trace.get_tracer(__name__)
    
    # Create Jaeger exporter
    jaeger_exporter = JaegerExporter(
        agent_host_name="jaeger",
        agent_port=6831,
    )
    
    # Create span processor
    span_processor = BatchSpanProcessor(jaeger_exporter)
    trace.get_tracer_provider().add_span_processor(span_processor)
    
    return tracer

# Usage in application
def process_federation_envelope(envelope_data: bytes, stage_instance: str):
    """Process federation envelope with tracing."""
    tracer = trace.get_tracer(__name__)
    
    with tracer.start_as_current_span("process_federation_envelope") as span:
        span.set_attribute("stage_instance", stage_instance)
        span.set_attribute("envelope_size", len(envelope_data))
        
        # Process envelope
        result = _process_envelope(envelope_data)
        
        span.set_attribute("result", result)
        return result
```

## 📊 **Performance Monitoring**

### **Key Performance Indicators (KPIs)**

```python
# KPI definitions
class PerformanceKPIs:
    # Response time targets
    TARGET_RESPONSE_TIME_95TH = 0.5  # 500ms
    TARGET_RESPONSE_TIME_99TH = 1.0  # 1s
    
    # Throughput targets
    TARGET_REQUESTS_PER_SECOND = 100
    TARGET_CONCURRENT_USERS = 1000
    
    # Error rate targets
    TARGET_ERROR_RATE = 0.01  # 1%
    TARGET_AVAILABILITY = 0.999  # 99.9%
    
    # Resource utilization targets
    TARGET_CPU_USAGE = 0.8  # 80%
    TARGET_MEMORY_USAGE = 0.8  # 80%
    TARGET_DISK_USAGE = 0.9  # 90%

# Performance monitoring
def monitor_performance():
    """Monitor key performance indicators."""
    metrics = {
        'response_time_95th': get_response_time_95th(),
        'response_time_99th': get_response_time_99th(),
        'requests_per_second': get_requests_per_second(),
        'error_rate': get_error_rate(),
        'availability': get_availability(),
        'cpu_usage': get_cpu_usage(),
        'memory_usage': get_memory_usage(),
        'disk_usage': get_disk_usage()
    }
    
    # Check against targets
    alerts = []
    if metrics['response_time_95th'] > PerformanceKPIs.TARGET_RESPONSE_TIME_95TH:
        alerts.append("Response time 95th percentile exceeds target")
    
    if metrics['error_rate'] > PerformanceKPIs.TARGET_ERROR_RATE:
        alerts.append("Error rate exceeds target")
    
    return metrics, alerts
```

## 🛠️ **Monitoring Tools**

### **Prometheus Configuration**

```yaml
# monitoring/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "rules/*.yml"

scrape_configs:
  - job_name: 'chorus-bridge'
    static_configs:
      - targets: ['bridge:9090']
    metrics_path: /metrics
    scrape_interval: 5s
    scrape_timeout: 5s

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres:9187']
    scrape_interval: 15s

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']
    scrape_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093
```

### **Grafana Configuration**

```yaml
# monitoring/grafana/datasources/prometheus.yml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
```

## 📚 **Additional Resources**

- **[Deployment Guide](./Deployment-Guide.md)** - Production deployment with monitoring
- **[Configuration Guide](./Configuration-Guide.md)** - Monitoring configuration options
- **[Security Guide](./Security-Guide.md)** - Security monitoring and alerting
- **[Troubleshooting Guide](./Troubleshooting-Guide.md)** - Monitoring troubleshooting

---

*This monitoring guide provides comprehensive coverage of all monitoring and observability aspects for the Chorus Bridge.*
