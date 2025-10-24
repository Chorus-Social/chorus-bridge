# Chorus Bridge - Security Guide

## 🛡️ **Security Overview**

The Chorus Bridge implements a comprehensive security model designed to protect the federation layer while maintaining the network's core principles of anonymity and decentralization.

## 🔐 **Security Architecture**

### **Multi-Layer Security Model**

```
┌─────────────────────────────────────────────────────────────┐
│                    Security Layers                         │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: Network Security (TLS, mTLS, Firewall)          │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: Authentication (JWT, Ed25519 Signatures)        │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: Authorization (Trust Store, Blacklist)         │
├─────────────────────────────────────────────────────────────┤
│  Layer 4: Data Integrity (Signatures, Hashing, Replay)    │
├─────────────────────────────────────────────────────────────┤
│  Layer 5: Application Security (Rate Limiting, Validation)│
└─────────────────────────────────────────────────────────────┘
```

### **Security Principles**

1. **Defense in Depth** - Multiple security layers
2. **Zero Trust Architecture** - Verify everything, trust nothing
3. **Cryptographic Security** - Strong encryption and signatures
4. **Anonymity Preservation** - No real-world timestamps or identifiers
5. **Data Minimization** - Collect only necessary information

## 🔑 **Authentication & Authorization**

### **JWT Authentication**

The bridge uses JWT tokens for API authentication:

```python
# JWT Token Structure
{
  "sub": "stage_instance_id",      # Subject (instance identifier)
  "iat": 1640995200,              # Issued at timestamp
  "exp": 1640998800,              # Expiration timestamp
  "jti": "unique_token_id"        # JWT ID for replay protection
}
```

**Security Features:**
- **Ed25519 Signatures** - Cryptographically secure signing
- **Short Expiration** - Tokens expire quickly (1 hour default)
- **Unique JTI** - Prevents token replay attacks
- **Instance Binding** - Tokens tied to specific instances

### **Trust Store Management**

The bridge maintains a trust store of authorized instances:

```json
{
  "stage-001": "ed25519_public_key_1_hex",
  "stage-002": "ed25519_public_key_2_hex",
  "stage-003": "ed25519_public_key_3_hex"
}
```

**Trust Store Features:**
- **Public Key Storage** - Ed25519 public keys for verification
- **Instance Identity** - Unique identifiers for each instance
- **Dynamic Updates** - Trust store can be updated without restart
- **Blacklist Support** - Malicious instances can be blocked

### **Blacklist Management**

The bridge supports blacklisting malicious instances:

```python
# Blacklist operations
trust_store.add_to_blacklist("malicious-stage-001", "reason_hash")
trust_store.is_blacklisted("stage-001")  # Returns True/False
trust_store.remove_from_blacklist("stage-001")
```

**Blacklist Features:**
- **Reason Tracking** - Cryptographic hashes of blacklist reasons
- **Automatic Enforcement** - Blacklisted instances are rejected
- **Audit Trail** - All blacklist operations are logged
- **Recovery Support** - Instances can be removed from blacklist

## 🔒 **Cryptographic Security**

### **Ed25519 Signatures**

All federation messages are signed using Ed25519:

```python
import nacl.signing
import nacl.encoding

# Generate key pair
signing_key = nacl.signing.SigningKey.generate()
verify_key = signing_key.verify_key

# Sign message
message = b"federation_envelope_data"
signed_message = signing_key.sign(message)
signature = signed_message.signature

# Verify signature
try:
    verify_key.verify(signed_message)
    print("Signature is valid")
except nacl.exceptions.BadSignatureError:
    print("Signature is invalid")
```

**Ed25519 Benefits:**
- **High Performance** - Fast signing and verification
- **Small Signatures** - 64-byte signatures
- **Security** - 128-bit security level
- **Deterministic** - Same input always produces same signature

### **Message Integrity**

All federation messages include integrity protection:

```python
# Message integrity verification
def verify_message_integrity(envelope: FederationEnvelope) -> bool:
    # Extract signature and message data
    signature = envelope.signature
    message_data = envelope.serialize()
    
    # Get sender's public key
    sender_id = envelope.sender_instance_id
    public_key = trust_store.get_public_key(sender_id)
    
    # Verify signature
    try:
        public_key.verify(message_data, signature)
        return True
    except nacl.exceptions.BadSignatureError:
        return False
```

### **Replay Protection**

The bridge implements replay protection to prevent message replay attacks:

```python
# Replay protection
class ReplayProtection:
    def __init__(self, ttl_seconds: int = 86400):
        self.cache = {}
        self.ttl = ttl_seconds
    
    def is_replay(self, message_id: str) -> bool:
        if message_id in self.cache:
            return True
        
        self.cache[message_id] = time.time()
        return False
    
    def cleanup_expired(self):
        current_time = time.time()
        expired_keys = [
            key for key, timestamp in self.cache.items()
            if current_time - timestamp > self.ttl
        ]
        for key in expired_keys:
            del self.cache[key]
```

## 🌐 **Network Security**

### **TLS Configuration**

The bridge enforces TLS for all external communications:

```nginx
# nginx.conf - TLS configuration
server {
    listen 443 ssl http2;
    server_name bridge.chorus.network;
    
    # SSL configuration
    ssl_certificate /etc/ssl/certs/cert.pem;
    ssl_certificate_key /etc/ssl/private/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Content-Security-Policy "default-src 'self'" always;
}
```

### **Firewall Configuration**

```bash
# UFW firewall rules
ufw default deny incoming
ufw default allow outgoing

# Allow SSH
ufw allow 22/tcp

# Allow HTTP/HTTPS
ufw allow 80/tcp
ufw allow 443/tcp

# Allow PostgreSQL (if needed)
ufw allow from 10.0.0.0/8 to any port 5432

# Enable firewall
ufw enable
```

### **Network Segmentation**

```
┌─────────────────────────────────────────────────────────────┐
│                    Network Segmentation                     │
├─────────────────────────────────────────────────────────────┤
│  Internet → Load Balancer → Bridge Instances              │
├─────────────────────────────────────────────────────────────┤
│  Bridge Instances → Database (Private Network)            │
├─────────────────────────────────────────────────────────────┤
│  Bridge Instances → Conductor (TLS/mTLS)                  │
├─────────────────────────────────────────────────────────────┤
│  Monitoring → Prometheus/Grafana (Private Network)        │
└─────────────────────────────────────────────────────────────┘
```

## 🚫 **Rate Limiting & DDoS Protection**

### **Rate Limiting Configuration**

```python
# Rate limiting settings
RATE_LIMITS = {
    "federation_send": {
        "requests_per_second": 10,
        "burst": 50,
        "window": 60
    },
    "day_proof": {
        "requests_per_second": 5,
        "burst": 20,
        "window": 60
    },
    "activitypub_export": {
        "requests_per_second": 2,
        "burst": 10,
        "window": 60
    },
    "moderation_event": {
        "requests_per_second": 5,
        "burst": 25,
        "window": 60
    }
}
```

### **DDoS Protection**

```python
# DDoS protection implementation
class DDoSProtection:
    def __init__(self):
        self.rate_limiter = RateLimiter()
        self.circuit_breaker = CircuitBreaker()
    
    def check_request(self, client_ip: str, endpoint: str) -> bool:
        # Check rate limits
        if not self.rate_limiter.is_allowed(client_ip, endpoint):
            return False
        
        # Check circuit breaker
        if self.circuit_breaker.is_open():
            return False
        
        return True
```

## 🔍 **Input Validation & Sanitization**

### **Request Validation**

```python
# Input validation
from pydantic import BaseModel, validator
from typing import Optional

class FederationRequest(BaseModel):
    envelope_data: bytes
    stage_instance: str
    idempotency_key: Optional[str] = None
    
    @validator('stage_instance')
    def validate_stage_instance(cls, v):
        if not v or len(v) < 3:
            raise ValueError('Invalid stage instance ID')
        return v
    
    @validator('envelope_data')
    def validate_envelope_data(cls, v):
        if not v or len(v) < 100:
            raise ValueError('Invalid envelope data')
        return v
```

### **Content Sanitization**

```python
# Content sanitization
import re
import html

def sanitize_content(content: str) -> str:
    # Remove potentially dangerous characters
    content = re.sub(r'[<>"\']', '', content)
    
    # HTML escape remaining content
    content = html.escape(content)
    
    # Limit length
    if len(content) > 10000:
        content = content[:10000] + "..."
    
    return content
```

## 📊 **Audit Logging & Monitoring**

### **Security Event Logging**

```python
# Security event logging
import logging
import json
from datetime import datetime

security_logger = logging.getLogger('security')

def log_security_event(event_type: str, details: dict):
    event = {
        'timestamp': datetime.utcnow().isoformat(),
        'event_type': event_type,
        'details': details,
        'source_ip': request.client.host if request else None
    }
    
    security_logger.info(json.dumps(event))
```

**Logged Security Events:**
- **Authentication Failures** - Invalid JWT tokens
- **Authorization Denials** - Unauthorized access attempts
- **Signature Verification Failures** - Invalid message signatures
- **Rate Limit Violations** - Excessive request rates
- **Blacklist Events** - Blacklist additions/removals
- **Suspicious Activity** - Unusual patterns or behaviors

### **Security Metrics**

```python
# Security metrics
from prometheus_client import Counter, Histogram

# Security event counters
security_events_total = Counter(
    'bridge_security_events_total',
    'Total number of security events',
    ['event_type', 'severity']
)

# Authentication metrics
auth_failures_total = Counter(
    'bridge_auth_failures_total',
    'Total number of authentication failures',
    ['reason']
)

# Rate limiting metrics
rate_limit_violations_total = Counter(
    'bridge_rate_limit_violations_total',
    'Total number of rate limit violations',
    ['endpoint', 'client_ip']
)
```

## 🚨 **Incident Response**

### **Security Incident Classification**

| Severity | Description | Response Time | Actions |
|----------|-------------|---------------|---------|
| **Critical** | Active attack, data breach | 15 minutes | Immediate isolation, investigation |
| **High** | Suspicious activity, potential breach | 1 hour | Enhanced monitoring, analysis |
| **Medium** | Policy violations, anomalies | 4 hours | Investigation, documentation |
| **Low** | Minor issues, false positives | 24 hours | Review, documentation |

### **Incident Response Procedures**

1. **Detection** - Automated monitoring and alerting
2. **Assessment** - Determine severity and impact
3. **Containment** - Isolate affected systems
4. **Investigation** - Analyze logs and evidence
5. **Recovery** - Restore normal operations
6. **Documentation** - Record incident details
7. **Post-Incident** - Review and improve security

### **Automated Response**

```python
# Automated security response
class SecurityResponse:
    def __init__(self):
        self.alert_thresholds = {
            'auth_failures': 10,
            'rate_limit_violations': 50,
            'signature_failures': 5
        }
    
    def check_thresholds(self, metrics: dict):
        for metric, threshold in self.alert_thresholds.items():
            if metrics.get(metric, 0) > threshold:
                self.trigger_alert(metric, metrics[metric])
    
    def trigger_alert(self, metric: str, value: int):
        # Send alert to security team
        self.send_alert(f"Security threshold exceeded: {metric} = {value}")
        
        # Take automated action if critical
        if metric == 'auth_failures' and value > 20:
            self.block_suspicious_ips()
```

## 🔐 **Key Management**

### **JWT Signing Key Management**

```python
# Key rotation procedure
class KeyManager:
    def __init__(self):
        self.current_key = self.load_current_key()
        self.old_keys = self.load_old_keys()
    
    def rotate_key(self):
        # Generate new key
        new_key = nacl.signing.SigningKey.generate()
        
        # Store old key for verification
        self.old_keys.append(self.current_key)
        
        # Update current key
        self.current_key = new_key
        
        # Notify all instances
        self.notify_key_rotation(new_key)
    
    def verify_with_key(self, message: bytes, signature: bytes, key_id: str):
        if key_id == 'current':
            key = self.current_key.verify_key
        else:
            key = self.old_keys[int(key_id)].verify_key
        
        return key.verify(message, signature)
```

### **Trust Store Key Management**

```python
# Trust store key management
class TrustStoreManager:
    def add_instance(self, instance_id: str, public_key: str):
        # Validate public key format
        if not self.validate_public_key(public_key):
            raise ValueError("Invalid public key format")
        
        # Add to trust store
        self.trust_store[instance_id] = public_key
        
        # Log the addition
        self.log_key_addition(instance_id, public_key)
    
    def remove_instance(self, instance_id: str):
        if instance_id in self.trust_store:
            del self.trust_store[instance_id]
            self.log_key_removal(instance_id)
    
    def validate_public_key(self, public_key: str) -> bool:
        try:
            nacl.signing.VerifyKey(public_key.encode())
            return True
        except:
            return False
```

## 🧪 **Security Testing**

### **Penetration Testing**

```python
# Security test suite
import pytest
from unittest.mock import Mock

class TestSecurity:
    def test_jwt_authentication(self):
        # Test valid JWT
        valid_token = self.generate_valid_jwt()
        response = self.client.get('/health', headers={'Authorization': f'Bearer {valid_token}'})
        assert response.status_code == 200
        
        # Test invalid JWT
        invalid_token = 'invalid.jwt.token'
        response = self.client.get('/health', headers={'Authorization': f'Bearer {invalid_token}'})
        assert response.status_code == 401
    
    def test_rate_limiting(self):
        # Test rate limit enforcement
        for i in range(15):  # Exceed rate limit
            response = self.client.post('/api/bridge/federation/send')
            if i < 10:
                assert response.status_code in [200, 202]
            else:
                assert response.status_code == 429
    
    def test_signature_verification(self):
        # Test valid signature
        valid_envelope = self.create_valid_envelope()
        response = self.client.post('/api/bridge/federation/send', data=valid_envelope)
        assert response.status_code == 202
        
        # Test invalid signature
        invalid_envelope = self.create_invalid_envelope()
        response = self.client.post('/api/bridge/federation/send', data=invalid_envelope)
        assert response.status_code == 401
```

### **Security Scanning**

```bash
# Security scanning tools
# OWASP ZAP
docker run -t owasp/zap2docker-stable zap-baseline.py -t https://bridge.chorus.network

# Nmap port scanning
nmap -sS -O bridge.chorus.network

# SSL/TLS testing
testssl.sh bridge.chorus.network

# Dependency scanning
poetry run safety check
poetry run bandit -r src/
```

## 📚 **Security Best Practices**

### **Development Security**

1. **Secure Coding Practices**
   - Input validation and sanitization
   - Output encoding
   - Error handling without information disclosure
   - Secure random number generation

2. **Dependency Management**
   - Regular security updates
   - Vulnerability scanning
   - Minimal dependency footprint
   - Trusted sources only

3. **Code Review**
   - Security-focused code reviews
   - Automated security scanning
   - Threat modeling
   - Security testing

### **Operational Security**

1. **Access Control**
   - Principle of least privilege
   - Multi-factor authentication
   - Regular access reviews
   - Secure key management

2. **Monitoring & Logging**
   - Comprehensive security logging
   - Real-time monitoring
   - Automated alerting
   - Regular log analysis

3. **Incident Response**
   - Documented procedures
   - Regular drills
   - Post-incident reviews
   - Continuous improvement

## 📖 **Additional Resources**

- **[Configuration Guide](./Configuration-Guide.md)** - Security configuration options
- **[Deployment Guide](./Deployment-Guide.md)** - Secure deployment practices
- **[Monitoring Guide](./Monitoring-Guide.md)** - Security monitoring setup
- **[Troubleshooting Guide](./Troubleshooting-Guide.md)** - Security issue resolution

---

*This security guide provides comprehensive coverage of Chorus Bridge security implementation and best practices.*
