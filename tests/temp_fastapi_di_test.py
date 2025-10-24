from __future__ import annotations

import asyncio
from typing import Optional

import pytest
from fastapi import FastAPI, Depends, Header, HTTPException, status, APIRouter
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

# Mock BridgeSettings and BridgeRepository for JWTAuth
class MockBridgeSettings:
    def __init__(self):
        self.jwt_enforcement_enabled = True
        self.jwt_public_key = "test_public_key"
        self.instance_id = "test_instance"

class MockBridgeRepository:
    def remember_jti(self, jti: str, instance_id: str, exp: int) -> bool:
        return True # Always allow for mock

# Original JWTAuth class
class JWTAuth:
    def __init__(self, settings: MockBridgeSettings, repository: MockBridgeRepository):
        self.settings = settings
        self.repository = repository

    async def __call__(
        self,
        authorization: Optional[str] = Header(None),
        x_chorus_instance_id: Optional[str] = Header(None, alias="X-Chorus-Instance-Id"),
    ):
        if not self.settings.jwt_enforcement_enabled:
            return

        if authorization is None or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated: Missing or invalid Authorization header",
            )

        if x_chorus_instance_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing X-Chorus-Instance-Id header",
            )
        # Simplified JWT decode for testing
        if authorization != "Bearer valid_token" or x_chorus_instance_id != "test_instance":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid JWT token")

# Mock RateLimiter
class RateLimiter:
    def __init__(self, settings: MockBridgeSettings):
        self.settings = settings

    async def __call__(self):
        pass # Always allow for mock


# Dependency provider functions
@pytest.fixture(scope="module")
def mock_bridge_settings():
    return MockBridgeSettings()

@pytest.fixture(scope="module")
def mock_bridge_repository():
    return MockBridgeRepository()

def get_jwt_auth_dependency(settings: MockBridgeSettings = Depends(mock_bridge_settings), repository: MockBridgeRepository = Depends(mock_bridge_repository)) -> JWTAuth:
    return JWTAuth(settings, repository)

def get_rate_limiter_dependency(settings: MockBridgeSettings = Depends(mock_bridge_settings)) -> RateLimiter:
    return RateLimiter(settings)


# Minimal FastAPI app
app = FastAPI()

# Define a router for the test routes
test_router = APIRouter()

@test_router.get("/test-auth")
async def _test_auth_route(
    jwt_auth_dep: JWTAuth = Depends(get_jwt_auth_dependency),
    rate_limit_dep: RateLimiter = Depends(get_rate_limiter_dependency),
):
    return {"message": "Authenticated and rate-limited!"}

# Include the router in the main app
app.include_router(test_router)


@pytest.fixture(scope="module")
def test_app_client(mock_bridge_settings, mock_bridge_repository):
    # Create a new FastAPI app for each test module to ensure clean state
    test_app = FastAPI()
    test_app.dependency_overrides[get_jwt_auth_dependency] = lambda: JWTAuth(mock_bridge_settings, mock_bridge_repository)
    test_app.dependency_overrides[get_rate_limiter_dependency] = lambda: RateLimiter(mock_bridge_settings)
    test_app.include_router(test_router) # Include the router from the main app

    with TestClient(test_app) as client:
        yield client
    test_app.dependency_overrides = {} # Clear overrides after tests

@pytest.mark.asyncio
async def test_auth_success(test_app_client):
    response = test_app_client.get("/test-auth", headers={
        "Authorization": "Bearer valid_token",
        "X-Chorus-Instance-Id": "test_instance"
    })
    assert response.status_code == 200
    assert response.json() == {"message": "Authenticated and rate-limited!"}

@pytest.mark.asyncio
async def test_auth_missing_header(test_app_client):
    response = test_app_client.get("/test-auth")
    assert response.status_code == 401
    assert "Not authenticated" in response.json()["detail"]

@pytest.mark.asyncio
async def test_auth_invalid_token(test_app_client):
    response = test_app_client.get("/test-auth", headers={
        "Authorization": "Bearer invalid_token",
        "X-Chorus-Instance-Id": "test_instance"
    })
    assert response.status_code == 401
    assert "Invalid JWT token" in response.json()["detail"]
