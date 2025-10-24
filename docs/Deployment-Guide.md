# Chorus Bridge - Deployment Guide

## 🚀 **Production Deployment**

This guide covers deploying the Chorus Bridge to production environments with high availability, security, and monitoring.

## 🏗️ **Deployment Architecture**

### **Production Architecture**

```
┌─────────────────────────────────────────────────────────────┐
│                    Production Stack                        │
├─────────────────────────────────────────────────────────────┤
│  Load Balancer (Nginx/HAProxy)                             │
├─────────────────────────────────────────────────────────────┤
│  Chorus Bridge (3+ replicas)                               │
├─────────────────────────────────────────────────────────────┤
│  PostgreSQL (Primary + Read Replicas)                     │
├─────────────────────────────────────────────────────────────┤
│  Conductor Network (External)                              │
├─────────────────────────────────────────────────────────────┤
│  Monitoring (Prometheus + Grafana)                         │
└─────────────────────────────────────────────────────────────┘
```

### **High Availability Setup**

- **Load Balancer**: Distributes traffic across multiple bridge instances
- **Database**: Primary-replica setup with automatic failover
- **Monitoring**: Comprehensive observability with alerting
- **Security**: TLS termination, JWT authentication, rate limiting

## 🐳 **Docker Deployment**

### **Production Dockerfile**

```dockerfile
# Dockerfile
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --only=main --no-dev

# Copy application code
COPY src/ ./src/

# Create non-root user
RUN useradd -m -u 1000 bridge && chown -R bridge:bridge /app
USER bridge

# Expose ports
EXPOSE 8000 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start application
CMD ["python", "-m", "src.chorus_bridge"]
```

### **Docker Compose Production**

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  bridge:
    build: .
    ports:
      - "8000:8000"
      - "9090:9090"
    environment:
      - DATABASE_URL=postgresql://user:password@postgres:5432/chorus_bridge
      - CONDUCTOR_BASE_URL=https://conductor.chorus.network
      - JWT_SIGNING_KEY=${JWT_SIGNING_KEY}
      - TRUST_STORE_PATH=/app/trust_store.json
      - PROMETHEUS_PORT=9090
      - LOG_LEVEL=INFO
    volumes:
      - ./trust_store.json:/app/trust_store.json:ro
      - ./logs:/app/logs
    depends_on:
      - postgres
    restart: unless-stopped
    deploy:
      replicas: 3
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
        reservations:
          memory: 256M
          cpus: '0.25'

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=chorus_bridge
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./postgresql.conf:/etc/postgresql/postgresql.conf
    ports:
      - "5432:5432"
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '1.0'

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--web.enable-lifecycle'
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana:/etc/grafana/provisioning
    restart: unless-stopped

volumes:
  postgres_data:
  prometheus_data:
  grafana_data:
```

### **Deploy with Docker Compose**

```bash
# Set environment variables
export JWT_SIGNING_KEY="your_jwt_signing_key_here"
export POSTGRES_PASSWORD="secure_password"

# Deploy production stack
docker-compose -f docker-compose.prod.yml up -d

# Check status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f bridge
```

## ☸️ **Kubernetes Deployment**

### **Namespace**

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: chorus-bridge
  labels:
    name: chorus-bridge
```

### **ConfigMap**

```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: chorus-bridge-config
  namespace: chorus-bridge
data:
  DATABASE_URL: "postgresql://user:password@postgres:5432/chorus_bridge"
  CONDUCTOR_BASE_URL: "https://conductor.chorus.network"
  CONDUCTOR_MODE: "http"
  CONDUCTOR_PROTOCOL: "grpc"
  CONDUCTOR_MAX_RETRIES: "3"
  CONDUCTOR_RETRY_DELAY: "1.0"
  CONDUCTOR_TIMEOUT: "30.0"
  CONDUCTOR_CIRCUIT_BREAKER_THRESHOLD: "5"
  CONDUCTOR_CIRCUIT_BREAKER_TIMEOUT: "60.0"
  CONDUCTOR_CACHE_TTL: "300.0"
  CONDUCTOR_CACHE_SIZE: "1000"
  PROMETHEUS_PORT: "9090"
  LOG_LEVEL: "INFO"
```

### **Secret**

```yaml
# k8s/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: chorus-bridge-secrets
  namespace: chorus-bridge
type: Opaque
data:
  JWT_SIGNING_KEY: <base64_encoded_jwt_key>
  TRUST_STORE_JSON: <base64_encoded_trust_store>
  DATABASE_PASSWORD: <base64_encoded_db_password>
```

### **Deployment**

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: chorus-bridge
  namespace: chorus-bridge
  labels:
    app: chorus-bridge
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
          name: http
        - containerPort: 9090
          name: metrics
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
        - name: TRUST_STORE_JSON
          valueFrom:
            secretKeyRef:
              name: chorus-bridge-secrets
              key: TRUST_STORE_JSON
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

### **Service**

```yaml
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: chorus-bridge-service
  namespace: chorus-bridge
spec:
  selector:
    app: chorus-bridge
  ports:
  - name: http
    port: 8000
    targetPort: 8000
  - name: metrics
    port: 9090
    targetPort: 9090
  type: LoadBalancer
```

### **Ingress**

```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: chorus-bridge-ingress
  namespace: chorus-bridge
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - bridge.chorus.network
    secretName: chorus-bridge-tls
  rules:
  - host: bridge.chorus.network
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: chorus-bridge-service
            port:
              number: 8000
```

### **Deploy to Kubernetes**

```bash
# Create namespace
kubectl apply -f k8s/namespace.yaml

# Create secrets (update with your values)
kubectl create secret generic chorus-bridge-secrets \
  --from-literal=JWT_SIGNING_KEY="your_jwt_signing_key" \
  --from-literal=TRUST_STORE_JSON='{"stage-001":"public_key_1"}' \
  --from-literal=DATABASE_PASSWORD="secure_password" \
  -n chorus-bridge

# Deploy application
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml

# Check deployment
kubectl get pods -n chorus-bridge
kubectl get services -n chorus-bridge
kubectl get ingress -n chorus-bridge
```

## 🗄️ **Database Setup**

### **PostgreSQL Configuration**

```sql
-- postgresql.conf
# Connection settings
max_connections = 200
shared_buffers = 256MB
effective_cache_size = 1GB

# Logging
log_destination = 'stderr'
logging_collector = on
log_directory = 'pg_log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_statement = 'all'
log_min_duration_statement = 1000

# Performance
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
```

### **Database Initialization**

```bash
# Create database
createdb chorus_bridge

# Create user
psql -c "CREATE USER chorus_user WITH PASSWORD 'secure_password';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE chorus_bridge TO chorus_user;"

# Initialize schema
python -c "
from src.chorus_bridge.db import DatabaseSessionManager
from src.chorus_bridge.core.settings import BridgeSettings

settings = BridgeSettings()
db_manager = DatabaseSessionManager(settings.database_url)
db_manager.create_all()
print('Database schema created successfully!')
"
```

### **Database Backup**

```bash
# Create backup script
cat > backup_db.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/var/backups/chorus_bridge"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/chorus_bridge_$DATE.sql"

mkdir -p $BACKUP_DIR
pg_dump $DATABASE_URL > $BACKUP_FILE
gzip $BACKUP_FILE

# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete
EOF

chmod +x backup_db.sh

# Schedule daily backups
echo "0 2 * * * /path/to/backup_db.sh" | crontab -
```

## 🔒 **Security Configuration**

### **TLS/SSL Setup**

```bash
# Generate SSL certificates
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# Or use Let's Encrypt
certbot certonly --standalone -d bridge.chorus.network
```

### **Firewall Configuration**

```bash
# UFW configuration
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw allow 5432/tcp  # PostgreSQL (if needed)
ufw enable
```

### **Security Headers**

```nginx
# nginx.conf
server {
    listen 443 ssl;
    server_name bridge.chorus.network;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";
    add_header Content-Security-Policy "default-src 'self'";
    
    # SSL configuration
    ssl_certificate /etc/ssl/certs/cert.pem;
    ssl_certificate_key /etc/ssl/private/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_prefer_server_ciphers off;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 📊 **Monitoring Setup**

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

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres:9187']
    scrape_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093
```

### **Grafana Dashboard**

```json
{
  "dashboard": {
    "title": "Chorus Bridge Dashboard",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(bridge_events_received_total[5m])",
            "legendFormat": "Events/sec"
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
        ]
      },
      {
        "title": "Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(bridge_request_duration_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          }
        ]
      }
    ]
  }
}
```

### **Alerting Rules**

```yaml
# monitoring/rules/bridge.yml
groups:
- name: chorus-bridge
  rules:
  - alert: HighErrorRate
    expr: rate(bridge_events_failed_total[5m]) > 0.1
    for: 2m
    labels:
      severity: warning
    annotations:
      summary: "High error rate detected"
      description: "Error rate is {{ $value }} errors/sec"

  - alert: HighLatency
    expr: histogram_quantile(0.95, rate(bridge_request_duration_seconds_bucket[5m])) > 1
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High latency detected"
      description: "95th percentile latency is {{ $value }}s"

  - alert: ServiceDown
    expr: up{job="chorus-bridge"} == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Chorus Bridge service is down"
      description: "The Chorus Bridge service has been down for more than 1 minute"
```

## 🔄 **Deployment Automation**

### **CI/CD Pipeline**

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Build Docker image
      run: |
        docker build -t chorus/bridge:${{ github.sha }} .
        docker tag chorus/bridge:${{ github.sha }} chorus/bridge:latest
    
    - name: Deploy to Kubernetes
      run: |
        kubectl set image deployment/chorus-bridge bridge=chorus/bridge:${{ github.sha }} -n chorus-bridge
        kubectl rollout status deployment/chorus-bridge -n chorus-bridge
```

### **Health Checks**

```bash
# Health check script
#!/bin/bash
HEALTH_URL="https://bridge.chorus.network/health"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_URL)

if [ $RESPONSE -eq 200 ]; then
    echo "Health check passed"
    exit 0
else
    echo "Health check failed with status: $RESPONSE"
    exit 1
fi
```

## 🚨 **Troubleshooting**

### **Common Issues**

1. **Database Connection Issues**
   ```bash
   # Check database connectivity
   psql $DATABASE_URL -c "SELECT 1;"
   
   # Check database logs
   kubectl logs -f deployment/postgres -n chorus-bridge
   ```

2. **High Memory Usage**
   ```bash
   # Check memory usage
   kubectl top pods -n chorus-bridge
   
   # Adjust resource limits
   kubectl patch deployment chorus-bridge -n chorus-bridge -p '{"spec":{"template":{"spec":{"containers":[{"name":"bridge","resources":{"limits":{"memory":"1Gi"}}}]}}}}'
   ```

3. **Slow Response Times**
   ```bash
   # Check metrics
   curl https://bridge.chorus.network/metrics | grep bridge_request_duration
   
   # Check database performance
   kubectl exec -it deployment/postgres -n chorus-bridge -- psql -c "SELECT * FROM pg_stat_activity;"
   ```

### **Log Analysis**

```bash
# View application logs
kubectl logs -f deployment/chorus-bridge -n chorus-bridge

# Filter error logs
kubectl logs deployment/chorus-bridge -n chorus-bridge | grep ERROR

# Check specific pod
kubectl logs -f pod/chorus-bridge-xxx -n chorus-bridge
```

## 📚 **Additional Resources**

- **[Configuration Guide](./Configuration-Guide.md)** - Detailed configuration options
- **[Monitoring Guide](./Monitoring-Guide.md)** - Monitoring and observability
- **[Security Guide](./Security-Guide.md)** - Security best practices
- **[Troubleshooting Guide](./Troubleshooting-Guide.md)** - Common issues and solutions

---

*This deployment guide provides comprehensive instructions for deploying Chorus Bridge to production environments.*
