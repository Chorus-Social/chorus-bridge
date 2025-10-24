# Chorus Bridge - Troubleshooting Guide

## 🔧 **Troubleshooting Overview**

This guide provides comprehensive troubleshooting information for the Chorus Bridge, covering common issues, diagnostic procedures, and resolution steps.

## 🚨 **Common Issues**

### **Application Issues**

#### **1. Service Won't Start**

**Symptoms:**
- Application fails to start
- Error messages during startup
- Port binding issues

**Diagnosis:**
```bash
# Check application logs
docker logs chorus-bridge

# Check port availability
netstat -tulpn | grep :8000
lsof -i :8000

# Check configuration
python -c "from src.chorus_bridge.core.settings import BridgeSettings; print(BridgeSettings())"
```

**Solutions:**
```bash
# Kill process using port
sudo kill -9 $(lsof -t -i:8000)

# Check configuration file
cat .env

# Validate database connection
psql $DATABASE_URL -c "SELECT 1;"

# Check dependencies
poetry install --sync
```

#### **2. Database Connection Issues**

**Symptoms:**
- Database connection errors
- Timeout errors
- Connection pool exhaustion

**Diagnosis:**
```bash
# Test database connectivity
psql $DATABASE_URL -c "SELECT 1;"

# Check database status
sudo systemctl status postgresql

# Check connection pool
psql $DATABASE_URL -c "SELECT * FROM pg_stat_activity;"
```

**Solutions:**
```bash
# Restart database
sudo systemctl restart postgresql

# Check database configuration
sudo -u postgres psql -c "SHOW max_connections;"
sudo -u postgres psql -c "SHOW shared_buffers;"

# Increase connection limits
echo "max_connections = 200" >> /etc/postgresql/15/main/postgresql.conf
sudo systemctl reload postgresql
```

#### **3. Conductor Communication Issues**

**Symptoms:**
- Conductor request failures
- Circuit breaker open
- High latency to conductor

**Diagnosis:**
```bash
# Test conductor connectivity
curl -f $CONDUCTOR_BASE_URL/health

# Check conductor logs
kubectl logs -f deployment/conductor

# Check circuit breaker status
curl http://localhost:9090/metrics | grep circuit_breaker
```

**Solutions:**
```bash
# Reset circuit breaker
curl -X POST http://localhost:8000/admin/circuit-breaker/reset

# Check conductor configuration
echo $CONDUCTOR_BASE_URL
echo $CONDUCTOR_PROTOCOL

# Test with different conductor endpoint
export CONDUCTOR_BASE_URL=http://backup-conductor:8080
```

### **Performance Issues**

#### **1. High Response Times**

**Symptoms:**
- Slow API responses
- High latency metrics
- User complaints about slowness

**Diagnosis:**
```bash
# Check response times
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8000/health

# Check system resources
top
htop
iostat -x 1

# Check database performance
psql $DATABASE_URL -c "SELECT * FROM pg_stat_activity WHERE state = 'active';"
```

**Solutions:**
```bash
# Optimize database queries
psql $DATABASE_URL -c "ANALYZE;"
psql $DATABASE_URL -c "VACUUM;"

# Increase connection pool
export DATABASE_POOL_SIZE=50

# Add database indexes
psql $DATABASE_URL -c "CREATE INDEX CONCURRENTLY idx_envelope_timestamp ON envelope_cache(created_at);"
```

#### **2. High Memory Usage**

**Symptoms:**
- Out of memory errors
- Slow garbage collection
- System swapping

**Diagnosis:**
```bash
# Check memory usage
free -h
ps aux --sort=-%mem | head

# Check Python memory usage
python -c "import psutil; print(psutil.Process().memory_info().rss / 1024 / 1024)"

# Check garbage collection
python -c "import gc; print(gc.get_stats())"
```

**Solutions:**
```bash
# Increase memory limits
export PYTHONHASHSEED=0
export MALLOC_ARENA_MAX=2

# Optimize garbage collection
export PYTHONOPTIMIZE=1

# Restart with more memory
docker run --memory=2g chorus/bridge
```

#### **3. High CPU Usage**

**Symptoms:**
- High CPU utilization
- Slow response times
- System overheating

**Diagnosis:**
```bash
# Check CPU usage
top -p $(pgrep -f chorus-bridge)
htop

# Profile Python code
python -m cProfile -o profile.stats src/chorus_bridge/app.py
python -c "import pstats; pstats.Stats('profile.stats').sort_stats('cumulative').print_stats(10)"
```

**Solutions:**
```bash
# Optimize code
poetry run ruff check src/ --fix
poetry run mypy src/

# Reduce worker processes
export WORKER_PROCESSES=2

# Use async operations
# Replace synchronous calls with async equivalents
```

### **Security Issues**

#### **1. Authentication Failures**

**Symptoms:**
- JWT token validation errors
- 401 Unauthorized responses
- Signature verification failures

**Diagnosis:**
```bash
# Check JWT token
echo $JWT_SIGNING_KEY | base64 -d | hexdump -C

# Test JWT validation
python -c "
import jwt
from nacl.signing import SigningKey
key = SigningKey.from_seed(b'$JWT_SIGNING_KEY')
print('JWT key is valid')
"

# Check trust store
cat $TRUST_STORE_PATH
```

**Solutions:**
```bash
# Regenerate JWT key
python -c "
from nacl.signing import SigningKey
import base64
key = SigningKey.generate()
print('JWT_SIGNING_KEY=' + base64.b64encode(key.encode()).decode())
"

# Update trust store
echo '{"stage-001":"new_public_key"}' > $TRUST_STORE_PATH

# Restart application
docker restart chorus-bridge
```

#### **2. Rate Limiting Issues**

**Symptoms:**
- 429 Too Many Requests errors
- Legitimate requests being blocked
- Inconsistent rate limiting

**Diagnosis:**
```bash
# Check rate limit configuration
grep -r "RATE_LIMIT" .env

# Check rate limit metrics
curl http://localhost:9090/metrics | grep rate_limit

# Test rate limits
for i in {1..20}; do curl http://localhost:8000/health; done
```

**Solutions:**
```bash
# Adjust rate limits
export FEDERATION_SEND_RATE_LIMIT=20
export DAY_PROOF_RATE_LIMIT=10

# Reset rate limit counters
curl -X POST http://localhost:8000/admin/rate-limits/reset

# Check for misconfigured clients
grep "rate limit" /var/log/chorus-bridge/bridge.log
```

### **Network Issues**

#### **1. Connection Timeouts**

**Symptoms:**
- Connection timeout errors
- Slow network responses
- Intermittent connectivity

**Diagnosis:**
```bash
# Test network connectivity
ping conductor.chorus.network
telnet conductor.chorus.network 8080

# Check DNS resolution
nslookup conductor.chorus.network
dig conductor.chorus.network

# Check firewall rules
sudo ufw status
sudo iptables -L
```

**Solutions:**
```bash
# Update DNS settings
echo "nameserver 8.8.8.8" >> /etc/resolv.conf

# Configure firewall
sudo ufw allow 8080/tcp
sudo ufw allow 5432/tcp

# Check network configuration
ip route show
ip addr show
```

#### **2. SSL/TLS Issues**

**Symptoms:**
- SSL handshake failures
- Certificate errors
- TLS version mismatches

**Diagnosis:**
```bash
# Test SSL connection
openssl s_client -connect bridge.chorus.network:443

# Check certificate
openssl x509 -in cert.pem -text -noout

# Test TLS versions
nmap --script ssl-enum-ciphers -p 443 bridge.chorus.network
```

**Solutions:**
```bash
# Update certificates
certbot renew --dry-run
certbot renew

# Check TLS configuration
openssl ciphers -v 'ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS'

# Test SSL configuration
testssl.sh bridge.chorus.network
```

## 🔍 **Diagnostic Procedures**

### **Health Checks**

```bash
# Application health
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
curl http://localhost:8000/health/live

# Database health
psql $DATABASE_URL -c "SELECT 1;"

# Conductor health
curl $CONDUCTOR_BASE_URL/health

# System health
df -h
free -h
uptime
```

### **Log Analysis**

```bash
# Application logs
tail -f /var/log/chorus-bridge/bridge.log
grep "ERROR" /var/log/chorus-bridge/bridge.log
grep "WARNING" /var/log/chorus-bridge/bridge.log

# Database logs
sudo tail -f /var/log/postgresql/postgresql-15-main.log
sudo grep "ERROR" /var/log/postgresql/postgresql-15-main.log

# System logs
sudo journalctl -u chorus-bridge -f
sudo journalctl -u postgresql -f
```

### **Performance Analysis**

```bash
# CPU profiling
python -m cProfile -o profile.stats src/chorus_bridge/app.py
python -c "import pstats; pstats.Stats('profile.stats').sort_stats('cumulative').print_stats(20)"

# Memory profiling
python -m memory_profiler src/chorus_bridge/app.py

# Database performance
psql $DATABASE_URL -c "SELECT * FROM pg_stat_activity;"
psql $DATABASE_URL -c "SELECT * FROM pg_stat_database;"
psql $DATABASE_URL -c "SELECT * FROM pg_stat_user_tables;"
```

## 🛠️ **Debugging Tools**

### **Application Debugging**

```python
# Debug mode
export DEBUG=true
export LOG_LEVEL=DEBUG
export PYTHONPATH=.

# Start with debug output
python -m src.chorus_bridge

# Interactive debugging
python -c "
import pdb
from src.chorus_bridge.app import create_app
app = create_app()
pdb.set_trace()
"
```

### **Database Debugging**

```sql
-- Check database status
SELECT * FROM pg_stat_activity;
SELECT * FROM pg_stat_database;
SELECT * FROM pg_stat_user_tables;

-- Check slow queries
SELECT query, mean_time, calls 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;

-- Check locks
SELECT * FROM pg_locks;
SELECT * FROM pg_stat_activity WHERE state = 'waiting';
```

### **Network Debugging**

```bash
# Network connectivity
ping -c 4 conductor.chorus.network
traceroute conductor.chorus.network

# Port scanning
nmap -p 8000,5432,9090 localhost

# SSL debugging
openssl s_client -connect bridge.chorus.network:443 -debug

# HTTP debugging
curl -v http://localhost:8000/health
curl -v -H "Authorization: Bearer test_token" http://localhost:8000/api/bridge/federation/send
```

## 📊 **Monitoring and Alerting**

### **Key Metrics to Monitor**

```bash
# Application metrics
curl http://localhost:9090/metrics | grep bridge_

# System metrics
curl http://localhost:9090/metrics | grep node_

# Database metrics
curl http://localhost:9090/metrics | grep postgres_
```

### **Alert Thresholds**

```yaml
# Critical alerts
- Error rate > 5%
- Response time 95th percentile > 2s
- Memory usage > 90%
- CPU usage > 90%
- Database connections > 80% of max

# Warning alerts
- Error rate > 1%
- Response time 95th percentile > 1s
- Memory usage > 80%
- CPU usage > 80%
- Database connections > 60% of max
```

## 🔧 **Recovery Procedures**

### **Service Recovery**

```bash
# Restart application
docker restart chorus-bridge

# Restart database
sudo systemctl restart postgresql

# Restart monitoring
docker-compose restart prometheus grafana

# Full system restart
docker-compose down
docker-compose up -d
```

### **Data Recovery**

```bash
# Database backup
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql

# Database restore
psql $DATABASE_URL < backup_20240101_120000.sql

# Configuration backup
cp .env .env.backup
cp trust_store.json trust_store.json.backup
```

### **Disaster Recovery**

```bash
# Full system backup
tar -czf chorus-bridge-backup-$(date +%Y%m%d_%H%M%S).tar.gz \
  /var/lib/postgresql/data \
  /var/log/chorus-bridge \
  .env \
  trust_store.json

# Restore from backup
tar -xzf chorus-bridge-backup-20240101_120000.tar.gz
```

## 📚 **Additional Resources**

- **[Development Setup](./Development-Setup.md)** - Local development troubleshooting
- **[Deployment Guide](./Deployment-Guide.md)** - Production deployment issues
- **[Configuration Guide](./Configuration-Guide.md)** - Configuration troubleshooting
- **[Monitoring Guide](./Monitoring-Guide.md)** - Monitoring and alerting setup

---

*This troubleshooting guide provides comprehensive coverage of common issues and resolution procedures for the Chorus Bridge.*
