# Chorus Bridge - Production Ready

Chorus Bridge is now production-ready with comprehensive monitoring, security, and deployment configurations.

## 🚀 Quick Start

### Docker Compose (Recommended for Production)

```bash
# 1. Clone and configure
git clone https://github.com/Chorus-Social/chorus-bridge.git
cd chorus-bridge
cp env.example .env

# 2. Edit configuration
nano .env  # Update with your production values

# 3. Create trust store
cat > trust.json << EOF
{
  "instances": {
    "stage-1.chorus.social": "hex-encoded-ed25519-public-key",
    "stage-2.chorus.social": "hex-encoded-ed25519-public-key"
  }
}
EOF

# 4. Deploy
docker-compose -f docker-compose.prod.yml up -d

# 5. Verify
curl http://localhost:8000/health/ready
```

### Kubernetes Deployment

```bash
# 1. Apply configurations
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml

# 2. Check status
kubectl get pods -n chorus-bridge
kubectl get services -n chorus-bridge
```

## 📊 Monitoring & Observability

### Prometheus Metrics
- **Endpoint**: `http://localhost:9090/metrics`
- **Key Metrics**:
  - `bridge_events_received_total` - Federation events received
  - `bridge_events_processed_total` - Events processed successfully
  - `bridge_events_failed_total` - Failed events
  - `bridge_conductor_latency_seconds` - Conductor request latency
  - `bridge_peer_count` - Connected peers
  - `bridge_blacklist_size` - Blacklisted instances

### Grafana Dashboard
- **URL**: `http://localhost:3000`
- **Default Login**: admin/admin
- **Dashboard**: Chorus Bridge Dashboard (auto-configured)

### Health Checks
- **Liveness**: `GET /health/live`
- **Readiness**: `GET /health/ready`

## 🔧 Configuration

### Required Environment Variables

```bash
# Instance Identity
BRIDGE_INSTANCE_ID=your-bridge-instance-id

# Database
BRIDGE_DATABASE_URL=postgresql+psycopg://user:password@host:port/database

# Conductor Integration
BRIDGE_CONDUCTOR_MODE=http
BRIDGE_CONDUCTOR_BASE_URL=https://conductor.chorus.local:50051

# Security
BRIDGE_JWT_PUBLIC_KEY=your-jwt-public-key
BRIDGE_BRIDGE_PRIVATE_KEY=your-bridge-private-key

# ActivityPub
BRIDGE_ACTIVITYPUB_ACTOR_DOMAIN=bridge.chorus.social
```

### Trust Store Configuration

Create `trust.json` with trusted Stage instances:

```json
{
  "instances": {
    "stage-1.chorus.social": "hex-encoded-ed25519-public-key",
    "stage-2.chorus.social": "hex-encoded-ed25519-public-key"
  }
}
```

## 🛡️ Security Features

### Authentication & Authorization
- ✅ JWT-based authentication for Stage instances
- ✅ Ed25519 signature verification for all federation messages
- ✅ Rate limiting per instance
- ✅ Replay protection with nonce validation

### Network Security
- ✅ mTLS support for Conductor communication
- ✅ libp2p secure channels for P2P communication
- ✅ IP-based access controls (configurable)

### Data Protection
- ✅ No real-world timestamps stored or transmitted
- ✅ Content hashing for privacy-preserving federation
- ✅ Encrypted direct messages (E2E with NaCl)
- ✅ Secure key management

## 📈 Performance & Scaling

### Performance Targets
- **Federation Latency**: <5 seconds end-to-end
- **API Response Time**: <100ms for health checks
- **Database Queries**: <10ms average
- **Conductor Integration**: <3 seconds consensus

### Scaling Options
- **Horizontal Scaling**: Multiple Bridge instances behind load balancer
- **Database Scaling**: PostgreSQL with read replicas
- **Caching**: Redis for session and rate limiting data
- **CDN**: Static content delivery for ActivityPub exports

## 🔄 Operations

### Backup & Recovery
```bash
# Database backup
docker-compose -f docker-compose.prod.yml exec postgres pg_dump -U bridge chorus_bridge > backup.sql

# Restore from backup
docker-compose -f docker-compose.prod.yml exec -T postgres psql -U bridge chorus_bridge < backup.sql
```

### Updates
```bash
# Pull latest image
docker-compose -f docker-compose.prod.yml pull

# Rolling update
docker-compose -f docker-compose.prod.yml up -d --no-deps bridge
```

### Monitoring
```bash
# View logs
docker-compose -f docker-compose.prod.yml logs -f bridge

# Check metrics
curl http://localhost:9090/metrics | grep bridge_

# Health status
curl http://localhost:8000/health/ready
```

## 🚨 Troubleshooting

### Common Issues

1. **Database Connection Failed**
   ```bash
   # Check database connectivity
   docker-compose -f docker-compose.prod.yml exec bridge python -c "
   from sqlalchemy import create_engine
   engine = create_engine('$BRIDGE_DATABASE_URL')
   engine.connect()
   print('Database connection successful')
   "
   ```

2. **Conductor Connection Failed**
   ```bash
   # Test Conductor endpoint
   curl -k https://conductor.chorus.local:50051/health
   ```

3. **JWT Authentication Failed**
   ```bash
   # Verify JWT key format
   echo "$BRIDGE_JWT_PUBLIC_KEY" | xxd -r -p | base64
   ```

### Log Analysis
```bash
# Federation events
docker-compose -f docker-compose.prod.yml logs bridge | grep "FederationEnvelope"

# Errors
docker-compose -f docker-compose.prod.yml logs bridge | grep "ERROR"

# Performance
docker-compose -f docker-compose.prod.yml logs bridge | grep "latency"
```

## 📚 Additional Resources

- [Deployment Guide](DEPLOYMENT.md) - Detailed deployment instructions
- [API Documentation](docs/API.md) - Complete API reference
- [Architecture Overview](docs/Chorus-Architecture.md) - System architecture
- [Security Guide](docs/SECURITY.md) - Security best practices
- [Monitoring Guide](docs/MONITORING.md) - Monitoring and alerting setup

## 🤝 Support

- **GitHub Issues**: [Report bugs and request features](https://github.com/Chorus-Social/chorus-bridge/issues)
- **Documentation**: [Complete documentation](https://docs.chorus.social)
- **Community**: [Join the discussion](https://community.chorus.social)
- **Security**: [Report security issues](mailto:security@chorus.social)

---

**Chorus Bridge** - Production-ready federation layer for the Chorus ecosystem 🎵
