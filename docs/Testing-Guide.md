# Chorus Bridge - Testing Guide

## 🧪 **Testing Overview**

This guide covers comprehensive testing strategies for the Chorus Bridge, including unit tests, integration tests, performance tests, and security tests.

## 🏗️ **Testing Architecture**

### **Test Pyramid**

```
┌─────────────────────────────────────────────────────────────┐
│                    Test Pyramid                            │
├─────────────────────────────────────────────────────────────┤
│  E2E Tests (Few) - Full system integration tests          │
├─────────────────────────────────────────────────────────────┤
│  Integration Tests (Some) - Component interaction tests   │
├─────────────────────────────────────────────────────────────┤
│  Unit Tests (Many) - Individual component tests            │
└─────────────────────────────────────────────────────────────┘
```

### **Test Categories**

1. **Unit Tests** - Test individual functions and classes
2. **Integration Tests** - Test component interactions
3. **API Tests** - Test REST API endpoints
4. **Performance Tests** - Test system performance
5. **Security Tests** - Test security features
6. **End-to-End Tests** - Test complete workflows

## 🔧 **Test Setup**

### **Test Environment Configuration**

```python
# tests/conftest.py
import pytest
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.chorus_bridge.core.settings import BridgeSettings
from src.chorus_bridge.db import DatabaseSessionManager
from src.chorus_bridge.db.models import Base

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def test_settings():
    """Create test settings."""
    return BridgeSettings(
        database_url="postgresql://test:test@localhost:5432/chorus_bridge_test",
        conductor_mode="memory",
        prometheus_port=0,
        log_level="WARNING"
    )

@pytest.fixture
def test_db(test_settings):
    """Create test database."""
    engine = create_engine(test_settings.database_url)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)

@pytest.fixture
def test_session(test_db):
    """Create test database session."""
    Session = sessionmaker(bind=test_db)
    session = Session()
    yield session
    session.close()
```

### **Test Database Setup**

```python
# tests/db/conftest.py
import pytest
from src.chorus_bridge.db import DatabaseSessionManager
from src.chorus_bridge.core.settings import BridgeSettings

@pytest.fixture
def test_db_manager(test_settings):
    """Create test database manager."""
    db_manager = DatabaseSessionManager(test_settings.database_url)
    db_manager.create_all()
    yield db_manager
    db_manager.drop_all()
```

## 🧪 **Unit Tests**

### **Service Tests**

```python
# tests/services/test_bridge_service.py
import pytest
from unittest.mock import Mock, AsyncMock
from src.chorus_bridge.services.bridge import BridgeService
from src.chorus_bridge.core.settings import BridgeSettings
from src.chorus_bridge.core.trust import TrustStore

class TestBridgeService:
    @pytest.fixture
    def mock_settings(self):
        settings = Mock(spec=BridgeSettings)
        settings.federation_post_announce_enabled = True
        settings.federation_user_registration_enabled = True
        settings.federation_moderation_event_enabled = True
        settings.federation_day_proof_enabled = True
        settings.federation_instance_join_request_enabled = True
        settings.federation_community_creation_enabled = True
        settings.federation_user_update_enabled = True
        settings.federation_community_update_enabled = True
        settings.federation_community_membership_update_enabled = True
        settings.federation_blacklist_update_enabled = True
        return settings
    
    @pytest.fixture
    def mock_repository(self):
        repo = Mock()
        repo.remember_envelope = Mock(return_value=True)
        repo.remember_idempotency_key = Mock(return_value=True)
        return repo
    
    @pytest.fixture
    def mock_trust_store(self):
        return Mock(spec=TrustStore)
    
    @pytest.fixture
    def bridge_service(self, mock_settings, mock_repository, mock_trust_store):
        return BridgeService(
            settings=mock_settings,
            repository=mock_repository,
            trust_store=mock_trust_store
        )
    
    def test_process_federation_envelope_success(self, bridge_service, mock_repository):
        """Test successful federation envelope processing."""
        # Arrange
        envelope_data = b"test_envelope_data"
        stage_instance = "test-stage-001"
        
        # Act
        result = bridge_service.process_federation_envelope(envelope_data, stage_instance)
        
        # Assert
        assert result is True
        mock_repository.remember_envelope.assert_called_once()
    
    def test_process_federation_envelope_invalid_signature(self, bridge_service, mock_trust_store):
        """Test federation envelope with invalid signature."""
        # Arrange
        envelope_data = b"invalid_envelope_data"
        stage_instance = "unknown-stage"
        mock_trust_store.get_public_key.return_value = None
        
        # Act & Assert
        with pytest.raises(ValueError, match="Unknown instance"):
            bridge_service.process_federation_envelope(envelope_data, stage_instance)
```

### **API Tests**

```python
# tests/test_bridge_api.py
import pytest
from fastapi.testclient import TestClient
from src.chorus_bridge.app import create_app
from src.chorus_bridge.core.settings import BridgeSettings

class TestBridgeAPI:
    @pytest.fixture
    def test_settings(self):
        return BridgeSettings(
            database_url="postgresql://test:test@localhost:5432/chorus_bridge_test",
            conductor_mode="memory",
            prometheus_port=0,
            log_level="WARNING"
        )
    
    @pytest.fixture
    def test_app(self, test_settings):
        return create_app(test_settings)
    
    @pytest.fixture
    def test_client(self, test_app):
        return TestClient(test_app)
    
    def test_health_endpoint(self, test_client):
        """Test health check endpoint."""
        response = test_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_federation_send_success(self, test_client):
        """Test successful federation send."""
        # Arrange
        headers = {
            "Authorization": "Bearer test_jwt_token",
            "X-Chorus-Instance-Id": "test-stage-001",
            "Content-Type": "application/octet-stream"
        }
        data = b"test_envelope_data"
        
        # Act
        response = test_client.post("/api/bridge/federation/send", headers=headers, content=data)
        
        # Assert
        assert response.status_code == 202
        assert "event_id" in response.json()
    
    def test_federation_send_unauthorized(self, test_client):
        """Test federation send without authentication."""
        # Act
        response = test_client.post("/api/bridge/federation/send", content=b"test_data")
        
        # Assert
        assert response.status_code == 401
    
    def test_day_proof_endpoint(self, test_client):
        """Test day proof retrieval."""
        # Act
        response = test_client.get("/api/bridge/day-proof/12345")
        
        # Assert
        assert response.status_code == 200
        assert "day_number" in response.json()
```

## 🔗 **Integration Tests**

### **Database Integration Tests**

```python
# tests/integration/test_database.py
import pytest
from src.chorus_bridge.db import DatabaseSessionManager
from src.chorus_bridge.db.models import DayProofRecord
from src.chorus_bridge.core.settings import BridgeSettings

class TestDatabaseIntegration:
    @pytest.fixture
    def db_manager(self, test_settings):
        db_manager = DatabaseSessionManager(test_settings.database_url)
        db_manager.create_all()
        yield db_manager
        db_manager.drop_all()
    
    def test_day_proof_storage(self, db_manager):
        """Test day proof storage and retrieval."""
        # Arrange
        day_proof = DayProofRecord(
            day_number=12345,
            proof="test_proof_hash",
            proof_hash="test_proof_hash_sha256",
            canonical=True,
            source="conductor"
        )
        
        # Act
        with db_manager.session() as session:
            session.add(day_proof)
            session.commit()
            
            retrieved_proof = session.query(DayProofRecord).filter_by(day_number=12345).first()
        
        # Assert
        assert retrieved_proof is not None
        assert retrieved_proof.day_number == 12345
        assert retrieved_proof.proof == "test_proof_hash"
```

### **Conductor Integration Tests**

```python
# tests/integration/test_conductor.py
import pytest
from src.chorus_bridge.services.conductor import InMemoryConductorClient
from src.chorus_bridge.proto.federation_pb2 import DayProofRequest

class TestConductorIntegration:
    @pytest.fixture
    def conductor_client(self):
        return InMemoryConductorClient()
    
    def test_get_day_proof(self, conductor_client):
        """Test day proof retrieval from conductor."""
        # Act
        day_proof = conductor_client.get_day_proof(12345)
        
        # Assert
        assert day_proof is not None
        assert day_proof.day_number == 12345
    
    def test_submit_event(self, conductor_client):
        """Test event submission to conductor."""
        # Arrange
        event_data = b"test_event_data"
        
        # Act
        result = conductor_client.submit_event(event_data)
        
        # Assert
        assert result is True
```

## 🚀 **Performance Tests**

### **Load Testing**

```python
# tests/performance/test_load.py
import pytest
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from src.chorus_bridge.app import create_app
from src.chorus_bridge.core.settings import BridgeSettings

class TestLoadPerformance:
    @pytest.fixture
    def test_app(self):
        settings = BridgeSettings(
            database_url="postgresql://test:test@localhost:5432/chorus_bridge_test",
            conductor_mode="memory",
            prometheus_port=0
        )
        return create_app(settings)
    
    def test_concurrent_requests(self, test_app):
        """Test system performance under concurrent load."""
        from fastapi.testclient import TestClient
        client = TestClient(test_app)
        
        def make_request():
            response = client.get("/health")
            return response.status_code
        
        # Test with 100 concurrent requests
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(100)]
            results = [future.result() for future in futures]
        
        # Assert all requests succeeded
        assert all(status == 200 for status in results)
    
    def test_response_time(self, test_app):
        """Test response time under load."""
        from fastapi.testclient import TestClient
        client = TestClient(test_app)
        
        start_time = time.time()
        for _ in range(100):
            response = client.get("/health")
            assert response.status_code == 200
        end_time = time.time()
        
        avg_response_time = (end_time - start_time) / 100
        assert avg_response_time < 0.1  # Should be under 100ms
```

### **Memory Testing**

```python
# tests/performance/test_memory.py
import pytest
import psutil
import os
from src.chorus_bridge.app import create_app
from src.chorus_bridge.core.settings import BridgeSettings

class TestMemoryPerformance:
    def test_memory_usage(self):
        """Test memory usage under load."""
        settings = BridgeSettings(
            database_url="postgresql://test:test@localhost:5432/chorus_bridge_test",
            conductor_mode="memory",
            prometheus_port=0
        )
        
        app = create_app(settings)
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Simulate load
        from fastapi.testclient import TestClient
        client = TestClient(app)
        
        for _ in range(1000):
            response = client.get("/health")
            assert response.status_code == 200
        
        # Check memory usage
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 50MB)
        assert memory_increase < 50 * 1024 * 1024
```

## 🔒 **Security Tests**

### **Authentication Tests**

```python
# tests/security/test_authentication.py
import pytest
from fastapi.testclient import TestClient
from src.chorus_bridge.app import create_app
from src.chorus_bridge.core.settings import BridgeSettings

class TestAuthentication:
    @pytest.fixture
    def test_client(self):
        settings = BridgeSettings(
            database_url="postgresql://test:test@localhost:5432/chorus_bridge_test",
            conductor_mode="memory",
            prometheus_port=0
        )
        app = create_app(settings)
        return TestClient(app)
    
    def test_valid_jwt_authentication(self, test_client):
        """Test authentication with valid JWT token."""
        # This would require a properly signed JWT token
        headers = {"Authorization": "Bearer valid_jwt_token"}
        response = test_client.get("/health", headers=headers)
        assert response.status_code == 200
    
    def test_invalid_jwt_authentication(self, test_client):
        """Test authentication with invalid JWT token."""
        headers = {"Authorization": "Bearer invalid_token"}
        response = test_client.get("/health", headers=headers)
        assert response.status_code == 401
    
    def test_missing_authentication(self, test_client):
        """Test request without authentication."""
        response = test_client.get("/health")
        assert response.status_code == 401
```

### **Rate Limiting Tests**

```python
# tests/security/test_rate_limiting.py
import pytest
from fastapi.testclient import TestClient
from src.chorus_bridge.app import create_app
from src.chorus_bridge.core.settings import BridgeSettings

class TestRateLimiting:
    @pytest.fixture
    def test_client(self):
        settings = BridgeSettings(
            database_url="postgresql://test:test@localhost:5432/chorus_bridge_test",
            conductor_mode="memory",
            prometheus_port=0
        )
        app = create_app(settings)
        return TestClient(app)
    
    def test_rate_limit_enforcement(self, test_client):
        """Test rate limit enforcement."""
        # Make requests up to the rate limit
        for i in range(10):
            response = test_client.get("/health")
            assert response.status_code == 200
        
        # Exceed rate limit
        response = test_client.get("/health")
        assert response.status_code == 429
        assert "rate limit" in response.json()["detail"].lower()
```

## 🎯 **End-to-End Tests**

### **Complete Workflow Tests**

```python
# tests/e2e/test_workflows.py
import pytest
from fastapi.testclient import TestClient
from src.chorus_bridge.app import create_app
from src.chorus_bridge.core.settings import BridgeSettings

class TestEndToEndWorkflows:
    @pytest.fixture
    def test_client(self):
        settings = BridgeSettings(
            database_url="postgresql://test:test@localhost:5432/chorus_bridge_test",
            conductor_mode="memory",
            prometheus_port=0
        )
        app = create_app(settings)
        return TestClient(app)
    
    def test_federation_workflow(self, test_client):
        """Test complete federation workflow."""
        # 1. Send federation envelope
        headers = {
            "Authorization": "Bearer test_jwt_token",
            "X-Chorus-Instance-Id": "test-stage-001",
            "Content-Type": "application/octet-stream"
        }
        data = b"test_envelope_data"
        
        response = test_client.post("/api/bridge/federation/send", headers=headers, content=data)
        assert response.status_code == 202
        
        # 2. Get day proof
        response = test_client.get("/api/bridge/day-proof/12345")
        assert response.status_code == 200
        
        # 3. Export to ActivityPub
        export_data = {
            "chorus_post": {
                "post_id": "test_post_123",
                "author_pubkey": "test_author_key",
                "content": "Test post content",
                "creation_day": 12345
            },
            "target_instances": ["stage-002", "stage-003"]
        }
        
        response = test_client.post("/api/bridge/activitypub/export", json=export_data)
        assert response.status_code == 202
```

## 🧪 **Test Utilities**

### **Test Data Generators**

```python
# tests/utils/test_data.py
import uuid
import time
from typing import Dict, Any

class TestDataGenerator:
    @staticmethod
    def generate_federation_envelope() -> bytes:
        """Generate test federation envelope data."""
        return b"test_federation_envelope_data"
    
    @staticmethod
    def generate_jwt_token() -> str:
        """Generate test JWT token."""
        return "test_jwt_token"
    
    @staticmethod
    def generate_stage_instance() -> str:
        """Generate test stage instance ID."""
        return f"test-stage-{uuid.uuid4().hex[:8]}"
    
    @staticmethod
    def generate_chorus_post() -> Dict[str, Any]:
        """Generate test Chorus post data."""
        return {
            "post_id": f"post_{uuid.uuid4().hex[:8]}",
            "author_pubkey": f"author_key_{uuid.uuid4().hex[:8]}",
            "content": "Test post content",
            "creation_day": int(time.time())
        }
```

### **Test Fixtures**

```python
# tests/fixtures/test_fixtures.py
import pytest
from unittest.mock import Mock
from src.chorus_bridge.core.settings import BridgeSettings
from src.chorus_bridge.core.trust import TrustStore

@pytest.fixture
def mock_trust_store():
    """Create mock trust store."""
    trust_store = Mock(spec=TrustStore)
    trust_store.get_public_key.return_value = Mock()
    trust_store.is_blacklisted.return_value = False
    return trust_store

@pytest.fixture
def mock_conductor_client():
    """Create mock conductor client."""
    client = Mock()
    client.get_day_proof.return_value = Mock(day_number=12345, proof="test_proof")
    client.submit_event.return_value = True
    client.health_check.return_value = True
    return client
```

## 📊 **Test Coverage**

### **Coverage Configuration**

```python
# pytest.ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    --cov=src/chorus_bridge
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=80
```

### **Coverage Reports**

```bash
# Generate coverage report
poetry run pytest --cov=src/chorus_bridge --cov-report=html

# View coverage report
open htmlcov/index.html
```

## 🚀 **Test Execution**

### **Running Tests**

```bash
# Run all tests
poetry run pytest

# Run specific test file
poetry run pytest tests/test_bridge_api.py

# Run tests with coverage
poetry run pytest --cov=src/chorus_bridge

# Run tests in parallel
poetry run pytest -n auto

# Run tests with verbose output
poetry run pytest -v

# Run tests matching pattern
poetry run pytest -k "test_federation"
```

### **Continuous Integration**

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: chorus_bridge_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    
    - name: Install Poetry
      uses: snok/install-poetry@v1
    
    - name: Install dependencies
      run: poetry install
    
    - name: Run tests
      run: poetry run pytest --cov=src/chorus_bridge --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

## 📚 **Additional Resources**

- **[Development Setup](./Development-Setup.md)** - Local development environment
- **[API Reference](./API-Reference.md)** - API documentation for testing
- **[Configuration Guide](./Configuration-Guide.md)** - Test configuration options
- **[Troubleshooting Guide](./Troubleshooting-Guide.md)** - Test troubleshooting

---

*This testing guide provides comprehensive coverage of all testing strategies for the Chorus Bridge project.*
