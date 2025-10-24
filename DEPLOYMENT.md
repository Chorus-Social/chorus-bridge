# Chorus Bridge Deployment Guide

This guide provides step-by-step instructions for deploying Chorus Bridge to production.

## Prerequisites

- Docker and Docker Compose
- PostgreSQL database (or use the included PostgreSQL container)
- Conductor instance running and accessible
- SSL certificates for HTTPS (recommended)

## Quick Start

### 1. Clone and Configure

```bash
git clone https://github.com/Chorus-Social/chorus-bridge.git
cd chorus-bridge
cp env.example .env
```

### 2. Configure Environment

Edit `.env` file with your production values:

```bash
# Required: Update these values
BRIDGE_INSTANCE_ID=your-bridge-instance-id
BRIDGE_DATABASE_URL=postgresql+psycopg://user:password@host:port/database
BRIDGE_CONDUCTOR_BASE_URL=https://your-conductor-instance:50051
BRIDGE_JWT_PUBLIC_KEY=your-jwt-public-key
BRIDGE_BRIDGE_PRIVATE_KEY=your-bridge-private-key
BRIDGE_ACTIVITYPUB_ACTOR_DOMAIN=your-domain.com
```

### 3. Generate Trust Store

Create a `trust.json` file with trusted Stage instances:

```json
{
  "instances": {
    "stage-1.chorus.social": "hex-encoded-ed25519-public-key",
    "stage-2.chorus.social": "hex-encoded-ed25519-public-key"
  }
}
```

### 4. Deploy with Docker Compose

```bash
# Production deployment
docker-compose -f docker-compose.prod.yml up -d

# Check status
docker-compose -f docker-compose.prod.yml ps
```

### 5. Verify Deployment

```bash
# Health check
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready

# Metrics
curl http://localhost:9090/metrics
```

## Production Configuration

### Security Considerations

1. **Use HTTPS**: Configure reverse proxy (nginx/traefik) with SSL certificates
2. **Secure Database**: Use strong passwords and network isolation
3. **Key Management**: Store private keys securely (HashiCorp Vault, AWS KMS)
4. **Network Security**: Use firewalls and VPNs for internal communication

### Monitoring Setup

1. **Prometheus**: Metrics are exposed on port 9090
2. **Grafana**: Access on port 3000 (default password: admin)
3. **Logs**: Configure structured logging with ELK stack

### Scaling Considerations

- **Horizontal Scaling**: Run multiple Bridge instances behind a load balancer
- **Database**: Use PostgreSQL with read replicas for high availability
- **Caching**: Implement Redis for session and rate limiting data

## Kubernetes Deployment

### 1. Create Namespace

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: chorus-bridge
```

### 2. Deploy ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: bridge-config
  namespace: chorus-bridge
data:
  BRIDGE_INSTANCE_ID: "bridge-k8s"
  BRIDGE_CONDUCTOR_MODE: "http"
  BRIDGE_PROMETHEUS_PORT: "9090"
```

### 3. Deploy Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: bridge-secrets
  namespace: chorus-bridge
type: Opaque
data:
  database-url: <base64-encoded-database-url>
  jwt-public-key: <base64-encoded-jwt-public-key>
  bridge-private-key: <base64-encoded-bridge-private-key>
```

### 4. Deploy Application

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
        envFrom:
        - configMapRef:
            name: bridge-config
        - secretRef:
            name: bridge-secrets
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

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Check database URL and credentials
   - Ensure database is running and accessible
   - Verify network connectivity

2. **Conductor Connection Failed**
   - Verify Conductor endpoint is correct
   - Check network connectivity
   - Ensure Conductor is running and healthy

3. **JWT Authentication Failed**
   - Verify JWT public key is correct
   - Check key format (hex-encoded)
   - Ensure JWT enforcement is enabled

### Logs

```bash
# View application logs
docker-compose -f docker-compose.prod.yml logs -f bridge

# View specific service logs
docker-compose -f docker-compose.prod.yml logs -f postgres
```

### Metrics

Access Prometheus metrics at `http://localhost:9090/metrics`

Key metrics to monitor:
- `bridge_events_received_total`
- `bridge_events_processed_total`
- `bridge_events_failed_total`
- `bridge_conductor_latency_seconds`

## Maintenance

### Database Migrations

```bash
# Run migrations (if using Alembic)
docker-compose -f docker-compose.prod.yml exec bridge alembic upgrade head
```

### Backup

```bash
# Backup database
docker-compose -f docker-compose.prod.yml exec postgres pg_dump -U bridge chorus_bridge > backup.sql
```

### Updates

```bash
# Pull latest image
docker-compose -f docker-compose.prod.yml pull

# Restart services
docker-compose -f docker-compose.prod.yml up -d
```

## Support

For issues and questions:
- GitHub Issues: https://github.com/Chorus-Social/chorus-bridge/issues
- Documentation: https://docs.chorus.social
- Community: https://community.chorus.social
