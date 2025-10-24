# Chorus Bridge - Configuration Guide

## ⚙️ **Configuration Overview**

The Chorus Bridge uses a comprehensive configuration system based on Pydantic settings, supporting environment variables, configuration files, and runtime configuration. This guide covers all configuration options and best practices.

## 🔧 **Configuration Sources**

Configuration is loaded in the following order (later sources override earlier ones):

1. **Default values** (defined in code)
2. **Environment variables**
3. **Configuration files** (`.env`, `config.yaml`)
4. **Runtime configuration** (programmatic overrides)

## 📁 **Configuration Files**

### **Environment File (.env)**

Create a `.env` file in the project root:

```bash
# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/chorus_bridge

# Conductor Configuration
CONDUCTOR_MODE=http
CONDUCTOR_PROTOCOL=grpc
CONDUCTOR_BASE_URL=http://conductor:8080

# Security Configuration
JWT_SIGNING_KEY=your_jwt_signing_key_here
TRUST_STORE_PATH=/path/to/trust_store.json

# Performance Configuration
CONDUCTOR_MAX_RETRIES=3
CONDUCTOR_RETRY_DELAY=1.0
CONDUCTOR_TIMEOUT=30.0

# Caching Configuration
CONDUCTOR_CACHE_TTL=300.0
CONDUCTOR_CACHE_SIZE=1000

# Monitoring Configuration
PROMETHEUS_PORT=9090
LOG_LEVEL=INFO
```

### **Configuration File (config.yaml)**

Create a `config.yaml` file for complex configurations:

```yaml
database:
  url: "postgresql://user:password@localhost:5432/chorus_bridge"
  pool_size: 20
  max_overflow: 30

conductor:
  mode: "http"
  protocol: "grpc"
  base_url: "http://conductor:8080"
  max_retries: 3
  retry_delay: 1.0
  timeout: 30.0
  circuit_breaker:
    threshold: 5
    timeout: 60.0

security:
  jwt_signing_key: "your_jwt_signing_key_here"
  trust_store_path: "/path/to/trust_store.json"
  rate_limiting:
    default_rps: 10
    burst: 50

caching:
  conductor_cache_ttl: 300.0
  conductor_cache_size: 1000
  replay_cache_ttl: 86400

monitoring:
  prometheus_port: 9090
  log_level: "INFO"
  metrics_enabled: true
```

## 🔐 **Security Configuration**

### **JWT Configuration**

```python
# JWT Signing Key (Ed25519)
JWT_SIGNING_KEY=your_ed25519_private_key_here

# JWT Token Settings
JWT_ALGORITHM=EdDSA
JWT_EXPIRATION=3600  # 1 hour
JWT_ISSUER=chorus-bridge
```

### **Trust Store Configuration**

```json
{
  "stage-001": "ed25519_public_key_1_hex",
  "stage-002": "ed25519_public_key_2_hex",
  "stage-003": "ed25519_public_key_3_hex"
}
```

### **Rate Limiting Configuration**

```python
# Global rate limiting
FEDERATION_RATE_LIMITS_DEFAULT_RPS=10
FEDERATION_RATE_LIMITS_BURST=50

# Per-endpoint rate limiting
FEDERATION_SEND_RATE_LIMIT=10  # requests per second
DAY_PROOF_RATE_LIMIT=5
ACTIVITYPUB_EXPORT_RATE_LIMIT=2
MODERATION_EVENT_RATE_LIMIT=5
```

## 🗄️ **Database Configuration**

### **PostgreSQL Configuration**

```python
# Database URL
DATABASE_URL=postgresql://user:password@localhost:5432/chorus_bridge

# Connection Pool Settings
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=3600

# SSL Configuration
DATABASE_SSL_MODE=require
DATABASE_SSL_CERT=/path/to/client-cert.pem
DATABASE_SSL_KEY=/path/to/client-key.pem
DATABASE_SSL_ROOT_CERT=/path/to/ca-cert.pem
```

### **Database Schema Configuration**

```python
# Schema Management
DATABASE_AUTO_CREATE_TABLES=true
DATABASE_MIGRATION_PATH=/path/to/migrations

# Index Configuration
DATABASE_INDEX_ENABLED=true
DATABASE_INDEX_CLEANUP_INTERVAL=3600
```

## 🌐 **Conductor Configuration**

### **Conductor Connection Settings**

```python
# Conductor Mode
CONDUCTOR_MODE=http  # http, memory

# Conductor Protocol
CONDUCTOR_PROTOCOL=grpc  # http, grpc

# Conductor URL
CONDUCTOR_BASE_URL=http://conductor:8080

# Connection Settings
CONDUCTOR_MAX_RETRIES=3
CONDUCTOR_RETRY_DELAY=1.0
CONDUCTOR_TIMEOUT=30.0
CONDUCTOR_CONNECTION_TIMEOUT=30.0
```

### **Circuit Breaker Configuration**

```python
# Circuit Breaker Settings
CONDUCTOR_CIRCUIT_BREAKER_THRESHOLD=5
CONDUCTOR_CIRCUIT_BREAKER_TIMEOUT=60.0

# Health Check Settings
CONDUCTOR_HEALTH_CHECK_INTERVAL=30.0
CONDUCTOR_HEALTH_CHECK_TIMEOUT=5.0
```

### **gRPC Configuration**

```python
# gRPC Settings
GRPC_MAX_MESSAGE_LENGTH=4194304  # 4MB
GRPC_KEEPALIVE_TIME_MS=10000
GRPC_KEEPALIVE_TIMEOUT_MS=5000
GRPC_KEEPALIVE_PERMIT_WITHOUT_CALLS=true
GRPC_MAX_CONNECTION_IDLE_MS=30000
GRPC_MAX_CONNECTION_AGE_MS=300000
```

## 📊 **Caching Configuration**

### **Conductor Cache Settings**

```python
# Cache Configuration
CONDUCTOR_CACHE_TTL=300.0  # 5 minutes
CONDUCTOR_CACHE_SIZE=1000
CONDUCTOR_CACHE_CLEANUP_INTERVAL=60.0

# Cache Policies
CACHE_POLICY_LRU=true
CACHE_POLICY_TTL=true
CACHE_POLICY_MAX_SIZE=10000
```

### **Replay Protection Cache**

```python
# Replay Protection
REPLAY_CACHE_TTL_SECONDS=86400  # 24 hours
IDEMPOTENCY_TTL_SECONDS=3600   # 1 hour

# Cache Storage
REPLAY_CACHE_STORAGE=memory  # memory, redis
REDIS_URL=redis://localhost:6379/0
```

## 📈 **Performance Configuration**

### **Worker Configuration**

```python
# ActivityPub Worker
ACTIVITYPUB_WORKER_INTERVAL_SECONDS=60
ACTIVITYPUB_MAX_RETRIES=5
ACTIVITYPUB_RETRY_DELAY_SECONDS=60

# Outbound Federation Worker
OUTBOUND_FEDERATION_WORKER_INTERVAL=30
OUTBOUND_FEDERATION_MAX_RETRIES=3
OUTBOUND_FEDERATION_RETRY_DELAY=10
```

### **Connection Pool Configuration**

```python
# HTTP Client Pool
HTTP_POOL_SIZE=20
HTTP_MAX_CONNECTIONS=100
HTTP_KEEPALIVE_TIMEOUT=30.0

# gRPC Connection Pool
GRPC_POOL_SIZE=10
GRPC_MAX_CONNECTIONS=50
GRPC_CONNECTION_TIMEOUT=30.0
```

## 📊 **Monitoring Configuration**

### **Prometheus Configuration**

```python
# Prometheus Settings
PROMETHEUS_PORT=9090
PROMETHEUS_ENABLED=true
PROMETHEUS_METRICS_PATH=/metrics

# Metrics Configuration
METRICS_ENABLED=true
METRICS_COLLECTION_INTERVAL=60.0
METRICS_RETENTION_DAYS=30
```

### **Logging Configuration**

```python
# Logging Settings
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE=/var/log/chorus-bridge/bridge.log
LOG_MAX_SIZE=100MB
LOG_BACKUP_COUNT=5

# Structured Logging
LOG_STRUCTURED=true
LOG_INCLUDE_TIMESTAMP=true
LOG_INCLUDE_LEVEL=true
LOG_INCLUDE_LOGGER=true
```

### **Grafana Configuration**

```yaml
# Grafana Dashboard Configuration
grafana:
  enabled: true
  port: 3000
  admin_user: admin
  admin_password: admin
  dashboards:
    - name: "Chorus Bridge Dashboard"
      path: "/monitoring/grafana/dashboards/bridge-dashboard.json"
```

## 🐳 **Docker Configuration**

### **Docker Environment Variables**

```bash
# Container Configuration
CONTAINER_NAME=chorus-bridge
CONTAINER_IMAGE=chorus/bridge:latest
CONTAINER_PORT=8000

# Resource Limits
CONTAINER_MEMORY_LIMIT=512Mi
CONTAINER_CPU_LIMIT=500m
CONTAINER_MEMORY_REQUEST=256Mi
CONTAINER_CPU_REQUEST=250m
```

### **Docker Compose Configuration**

```yaml
version: '3.8'
services:
  bridge:
    image: chorus/bridge:latest
    environment:
      - DATABASE_URL=postgresql://user:password@postgres:5432/chorus_bridge
      - CONDUCTOR_BASE_URL=http://conductor:8080
      - PROMETHEUS_PORT=9090
    ports:
      - "8000:8000"
      - "9090:9090"
    depends_on:
      - postgres
      - conductor

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=chorus_bridge
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

## ☸️ **Kubernetes Configuration**

### **ConfigMap Configuration**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: chorus-bridge-config
  namespace: chorus-bridge
data:
  DATABASE_URL: "postgresql://user:password@postgres:5432/chorus_bridge"
  CONDUCTOR_BASE_URL: "http://conductor:8080"
  PROMETHEUS_PORT: "9090"
  LOG_LEVEL: "INFO"
  CONDUCTOR_CACHE_TTL: "300.0"
  CONDUCTOR_CACHE_SIZE: "1000"
```

### **Secret Configuration**

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: chorus-bridge-secrets
  namespace: chorus-bridge
type: Opaque
data:
  JWT_SIGNING_KEY: <base64_encoded_key>
  TRUST_STORE_JSON: <base64_encoded_trust_store>
  DATABASE_PASSWORD: <base64_encoded_password>
```

### **Deployment Configuration**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: chorus-bridge
  namespace: chorus-bridge
spec:
  replicas: 3
  selector:
    matchLabels:
      app: chorus-bridge
  template:
    metadata:
      labels:
        app: chorus-bridge
    spec:
      containers:
      - name: bridge
        image: chorus/bridge:latest
        ports:
        - containerPort: 8000
        - containerPort: 9090
        env:
        - name: DATABASE_URL
          valueFrom:
            configMapKeyRef:
              name: chorus-bridge-config
              key: DATABASE_URL
        - name: JWT_SIGNING_KEY
          valueFrom:
            secretKeyRef:
              name: chorus-bridge-secrets
              key: JWT_SIGNING_KEY
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

## 🔧 **Runtime Configuration**

### **Programmatic Configuration**

```python
from chorus_bridge.core.settings import BridgeSettings

# Create custom settings
settings = BridgeSettings(
    database_url="postgresql://user:password@localhost:5432/chorus_bridge",
    conductor_mode="http",
    conductor_protocol="grpc",
    conductor_base_url="http://conductor:8080",
    conductor_max_retries=5,
    conductor_retry_delay=2.0,
    conductor_timeout=60.0,
    conductor_circuit_breaker_threshold=10,
    conductor_circuit_breaker_timeout=120.0,
    conductor_cache_ttl=600.0,
    conductor_cache_size=2000,
    prometheus_port=9090,
    log_level="DEBUG"
)
```

### **Configuration Validation**

```python
# Validate configuration
try:
    settings = BridgeSettings()
    print("Configuration is valid")
except ValueError as e:
    print(f"Configuration error: {e}")
```

## 🧪 **Environment-Specific Configuration**

### **Development Environment**

```bash
# Development settings
NODE_ENV=development
LOG_LEVEL=DEBUG
DATABASE_URL=postgresql://localhost:5432/chorus_bridge_dev
CONDUCTOR_MODE=memory
PROMETHEUS_PORT=0  # Disable metrics
```

### **Testing Environment**

```bash
# Testing settings
NODE_ENV=test
LOG_LEVEL=WARNING
DATABASE_URL=postgresql://localhost:5432/chorus_bridge_test
CONDUCTOR_MODE=memory
PROMETHEUS_PORT=0
```

### **Production Environment**

```bash
# Production settings
NODE_ENV=production
LOG_LEVEL=INFO
DATABASE_URL=postgresql://user:password@db:5432/chorus_bridge
CONDUCTOR_MODE=http
CONDUCTOR_PROTOCOL=grpc
CONDUCTOR_BASE_URL=https://conductor.chorus.network
PROMETHEUS_PORT=9090
```

## 🔍 **Configuration Validation**

### **Required Settings**

The following settings are required for production:

```python
# Required settings
REQUIRED_SETTINGS = [
    "DATABASE_URL",
    "CONDUCTOR_BASE_URL",
    "JWT_SIGNING_KEY",
    "TRUST_STORE_PATH"
]
```

### **Configuration Validation Rules**

```python
# Validation rules
VALIDATION_RULES = {
    "CONDUCTOR_MAX_RETRIES": {"min": 0, "max": 10},
    "CONDUCTOR_RETRY_DELAY": {"min": 0.1, "max": 60.0},
    "CONDUCTOR_TIMEOUT": {"min": 1.0, "max": 300.0},
    "CONDUCTOR_CACHE_TTL": {"min": 60.0, "max": 3600.0},
    "CONDUCTOR_CACHE_SIZE": {"min": 100, "max": 10000}
}
```

## 📚 **Configuration Examples**

### **Minimal Configuration**

```bash
# Minimal required settings
DATABASE_URL=postgresql://user:password@localhost:5432/chorus_bridge
CONDUCTOR_BASE_URL=http://conductor:8080
JWT_SIGNING_KEY=your_jwt_signing_key_here
TRUST_STORE_PATH=/path/to/trust_store.json
```

### **High-Performance Configuration**

```bash
# High-performance settings
DATABASE_URL=postgresql://user:password@localhost:5432/chorus_bridge
CONDUCTOR_BASE_URL=http://conductor:8080
CONDUCTOR_MAX_RETRIES=5
CONDUCTOR_RETRY_DELAY=0.5
CONDUCTOR_TIMEOUT=60.0
CONDUCTOR_CACHE_TTL=600.0
CONDUCTOR_CACHE_SIZE=5000
PROMETHEUS_PORT=9090
```

### **High-Availability Configuration**

```bash
# High-availability settings
DATABASE_URL=postgresql://user:password@db-cluster:5432/chorus_bridge
CONDUCTOR_BASE_URL=http://conductor-cluster:8080
CONDUCTOR_CIRCUIT_BREAKER_THRESHOLD=3
CONDUCTOR_CIRCUIT_BREAKER_TIMEOUT=30.0
CONDUCTOR_HEALTH_CHECK_INTERVAL=10.0
```

## 🚨 **Configuration Troubleshooting**

### **Common Configuration Issues**

1. **Database Connection Issues**
   ```bash
   # Check database connectivity
   psql $DATABASE_URL -c "SELECT 1;"
   ```

2. **Conductor Connection Issues**
   ```bash
   # Test conductor connectivity
   curl -f $CONDUCTOR_BASE_URL/health
   ```

3. **JWT Key Issues**
   ```bash
   # Validate JWT key format
   python -c "from nacl.signing import SigningKey; SigningKey.from_seed(b'$JWT_SIGNING_KEY')"
   ```

### **Configuration Debugging**

```python
# Debug configuration loading
import logging
logging.basicConfig(level=logging.DEBUG)

from chorus_bridge.core.settings import BridgeSettings
settings = BridgeSettings()
print(f"Loaded settings: {settings.model_dump()}")
```

## 📖 **Additional Resources**

- **[Deployment Guide](./Deployment-Guide.md)** - Production deployment
- **[Security Guide](./Security-Guide.md)** - Security configuration
- **[Monitoring Guide](./Monitoring-Guide.md)** - Monitoring setup
- **[Troubleshooting Guide](./Troubleshooting-Guide.md)** - Common issues

---

*This configuration guide provides comprehensive coverage of all Chorus Bridge configuration options and best practices.*
