# Chorus Bridge - Development Setup

## 🚀 **Quick Start**

Get the Chorus Bridge running locally in minutes for development and testing.

## 📋 **Prerequisites**

### **System Requirements**

- **Python 3.11+** (recommended: Python 3.12)
- **Poetry** (dependency management)
- **PostgreSQL 15+** (database)
- **Docker & Docker Compose** (optional, for containerized development)
- **Git** (version control)

### **Development Tools**

- **IDE**: VS Code, PyCharm, or your preferred editor
- **Database Client**: pgAdmin, DBeaver, or psql
- **API Testing**: Postman, Insomnia, or curl
- **Monitoring**: Prometheus + Grafana (optional)

## 🛠️ **Installation**

### **1. Clone the Repository**

```bash
git clone https://github.com/chorus-network/chorus-bridge.git
cd chorus-bridge
```

### **2. Install Dependencies**

```bash
# Install Poetry if not already installed
curl -sSL https://install.python-poetry.org | python3 -

# Install project dependencies
poetry install

# Activate the virtual environment
poetry shell
```

### **3. Set Up Database**

```bash
# Start PostgreSQL (using Docker)
docker run --name chorus-postgres \
  -e POSTGRES_DB=chorus_bridge \
  -e POSTGRES_USER=chorus \
  -e POSTGRES_PASSWORD=chorus \
  -p 5432:5432 \
  -d postgres:15

# Or install PostgreSQL locally
# Ubuntu/Debian: sudo apt-get install postgresql-15
# macOS: brew install postgresql@15
# Windows: Download from https://www.postgresql.org/download/
```

### **4. Configure Environment**

```bash
# Copy environment template
cp env.example .env

# Edit configuration
nano .env
```

**Minimal `.env` configuration:**

```bash
# Database
DATABASE_URL=postgresql://chorus:chorus@localhost:5432/chorus_bridge

# Conductor (use in-memory for development)
CONDUCTOR_MODE=memory

# Security (generate your own keys)
JWT_SIGNING_KEY=your_jwt_signing_key_here
TRUST_STORE_PATH=./trust_store.json

# Development settings
LOG_LEVEL=DEBUG
PROMETHEUS_PORT=0  # Disable metrics in development
```

### **5. Initialize Database**

```bash
# Create database tables
poetry run python -c "
from src.chorus_bridge.db import DatabaseSessionManager
from src.chorus_bridge.core.settings import BridgeSettings

settings = BridgeSettings()
db_manager = DatabaseSessionManager(settings.database_url)
db_manager.create_all()
print('Database initialized successfully!')
"
```

### **6. Start the Development Server**

```bash
# Start the bridge
poetry run python -m src.chorus_bridge

# Or use uvicorn directly
poetry run uvicorn src.chorus_bridge.app:create_app --reload --host 0.0.0.0 --port 8000
```

The bridge will be available at `http://localhost:8000`

## 🐳 **Docker Development**

### **Using Docker Compose**

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f bridge

# Stop services
docker-compose down
```

### **Docker Compose Configuration**

```yaml
# docker-compose.dev.yml
version: '3.8'
services:
  bridge:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://chorus:chorus@postgres:5432/chorus_bridge
      - CONDUCTOR_MODE=memory
      - LOG_LEVEL=DEBUG
    depends_on:
      - postgres
    volumes:
      - ./src:/app/src
      - ./trust_store.json:/app/trust_store.json

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=chorus_bridge
      - POSTGRES_USER=chorus
      - POSTGRES_PASSWORD=chorus
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

## 🧪 **Testing Setup**

### **Run Tests**

```bash
# Run all tests
poetry run pytest

# Run specific test file
poetry run pytest tests/test_bridge_api.py

# Run with coverage
poetry run pytest --cov=src/chorus_bridge --cov-report=html

# Run with verbose output
poetry run pytest -v
```

### **Test Database**

```bash
# Create test database
createdb chorus_bridge_test

# Set test environment
export TEST_DATABASE_URL=postgresql://chorus:chorus@localhost:5432/chorus_bridge_test
```

### **Test Configuration**

```python
# tests/conftest.py
import pytest
from src.chorus_bridge.core.settings import BridgeSettings

@pytest.fixture
def test_settings():
    return BridgeSettings(
        database_url="postgresql://chorus:chorus@localhost:5432/chorus_bridge_test",
        conductor_mode="memory",
        prometheus_port=0,
        log_level="WARNING"
    )
```

## 🔧 **Development Tools**

### **Code Quality Tools**

```bash
# Format code
poetry run ruff format src/

# Lint code
poetry run ruff check src/

# Type checking
poetry run mypy src/

# Security scanning
poetry run bandit -r src/
```

### **Database Tools**

```bash
# Database migrations (when implemented)
poetry run alembic upgrade head

# Database shell
poetry run python -c "
from src.chorus_bridge.db import DatabaseSessionManager
from src.chorus_bridge.core.settings import BridgeSettings

settings = BridgeSettings()
db_manager = DatabaseSessionManager(settings.database_url)
# Use db_manager.session for database operations
"
```

### **API Testing**

```bash
# Test health endpoint
curl http://localhost:8000/health

# Test federation endpoint (requires JWT token)
curl -X POST http://localhost:8000/api/bridge/federation/send \
  -H "Authorization: Bearer <jwt_token>" \
  -H "X-Chorus-Instance-Id: test-stage" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @test_envelope.bin
```

## 📊 **Monitoring Setup**

### **Prometheus (Optional)**

```bash
# Start Prometheus
docker run --name prometheus \
  -p 9090:9090 \
  -v $(pwd)/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus

# Access Prometheus UI
open http://localhost:9090
```

### **Grafana (Optional)**

```bash
# Start Grafana
docker run --name grafana \
  -p 3000:3000 \
  -v $(pwd)/monitoring/grafana:/var/lib/grafana \
  grafana/grafana

# Access Grafana UI
open http://localhost:3000
# Default credentials: admin/admin
```

## 🔑 **Security Setup**

### **Generate JWT Signing Key**

```python
# Generate Ed25519 key pair
from nacl.signing import SigningKey
import base64

# Generate new key
signing_key = SigningKey.generate()
private_key = signing_key.encode()

# Save to environment
print(f"JWT_SIGNING_KEY={base64.b64encode(private_key).decode()}")
```

### **Create Trust Store**

```json
{
  "test-stage-001": "ed25519_public_key_1_hex",
  "test-stage-002": "ed25519_public_key_2_hex"
}
```

### **Generate Test JWT Token**

```python
# Generate test JWT token
import jwt
from nacl.signing import SigningKey
import base64

# Load signing key
signing_key = SigningKey.from_seed(base64.b64decode("your_jwt_signing_key_here"))

# Create JWT payload
payload = {
    "sub": "test-stage-001",
    "iat": 1640995200,
    "exp": 1640998800,
    "jti": "test-token-123"
}

# Sign and encode JWT
token = jwt.encode(payload, signing_key, algorithm="EdDSA")
print(f"JWT Token: {token}")
```

## 🐛 **Debugging**

### **Enable Debug Logging**

```bash
# Set debug log level
export LOG_LEVEL=DEBUG

# Start with debug output
poetry run python -m src.chorus_bridge
```

### **Database Debugging**

```python
# Enable SQL logging
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# Debug database queries
from src.chorus_bridge.db import DatabaseSessionManager
from src.chorus_bridge.core.settings import BridgeSettings

settings = BridgeSettings()
db_manager = DatabaseSessionManager(settings.database_url)

# Check database connection
with db_manager.session() as session:
    result = session.execute("SELECT 1").scalar()
    print(f"Database connection: {result}")
```

### **API Debugging**

```bash
# Enable request logging
export LOG_LEVEL=DEBUG

# Test with verbose curl
curl -v -X POST http://localhost:8000/api/bridge/federation/send \
  -H "Authorization: Bearer <jwt_token>" \
  -H "X-Chorus-Instance-Id: test-stage" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @test_envelope.bin
```

## 🔄 **Development Workflow**

### **1. Feature Development**

```bash
# Create feature branch
git checkout -b feature/new-feature

# Make changes
# ... edit code ...

# Run tests
poetry run pytest

# Format and lint
poetry run ruff format src/
poetry run ruff check src/

# Commit changes
git add .
git commit -m "Add new feature"
```

### **2. Code Review**

```bash
# Push branch
git push origin feature/new-feature

# Create pull request
# ... use GitHub/GitLab interface ...
```

### **3. Integration Testing**

```bash
# Test with real Conductor
export CONDUCTOR_MODE=http
export CONDUCTOR_BASE_URL=http://conductor:8080

# Run integration tests
poetry run pytest tests/integration/
```

## 📚 **Development Resources**

### **Useful Commands**

```bash
# Check code quality
poetry run ruff check src/ --statistics

# Run specific test
poetry run pytest tests/test_bridge_api.py::test_federation_send -v

# Generate test data
poetry run python scripts/generate_test_data.py

# Database backup
pg_dump $DATABASE_URL > backup.sql

# Database restore
psql $DATABASE_URL < backup.sql
```

### **IDE Configuration**

**VS Code Settings (`.vscode/settings.json`):**

```json
{
  "python.defaultInterpreterPath": "./venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "python.formatting.provider": "ruff",
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["tests/"]
}
```

**PyCharm Configuration:**

1. Set Python interpreter to Poetry virtual environment
2. Enable Ruff for linting
3. Configure pytest as test runner
4. Set up database connection for debugging

## 🚨 **Troubleshooting**

### **Common Issues**

1. **Database Connection Issues**
   ```bash
   # Check PostgreSQL status
   sudo systemctl status postgresql
   
   # Check database exists
   psql -U chorus -d chorus_bridge -c "SELECT 1;"
   ```

2. **Port Already in Use**
   ```bash
   # Find process using port
   lsof -i :8000
   
   # Kill process
   kill -9 <PID>
   ```

3. **Dependency Issues**
   ```bash
   # Reinstall dependencies
   poetry install --sync
   
   # Clear cache
   poetry cache clear --all pypi
   ```

4. **Permission Issues**
   ```bash
   # Fix file permissions
   chmod +x scripts/*
   
   # Fix database permissions
   sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE chorus_bridge TO chorus;"
   ```

### **Debug Mode**

```bash
# Enable debug mode
export DEBUG=true
export LOG_LEVEL=DEBUG
export PYTHONPATH=.

# Start with debug output
poetry run python -m src.chorus_bridge
```

## 📖 **Additional Resources**

- **[API Reference](./API-Reference.md)** - Complete API documentation
- **[Configuration Guide](./Configuration-Guide.md)** - Configuration options
- **[Testing Guide](./Testing-Guide.md)** - Testing strategies
- **[Troubleshooting Guide](./Troubleshooting-Guide.md)** - Common issues and solutions

---

*This development setup guide provides everything needed to get started with Chorus Bridge development.*
