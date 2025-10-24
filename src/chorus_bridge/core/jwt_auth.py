from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException, status
from jose import jwt, JOSEError

from chorus_bridge.core.settings import BridgeSettings
from chorus_bridge.db.repository import BridgeRepository


class JWTAuth:
    """JWT authentication and validation dependency for FastAPI.

    This class handles the verification of JWTs issued by Chorus Stage instances
    to authenticate requests to the Bridge. It performs signature verification,
    audience and issuer validation, expiration checks, and JTI replay protection.
    """

    def __init__(self, settings: BridgeSettings, repository: BridgeRepository):
        """Initializes the JWTAuth dependency.

        Args:
            settings: The BridgeSettings instance containing JWT configuration.
            repository: The BridgeRepository instance for JTI replay protection.
        """
        self.settings = settings
        self.repository = repository

    async def __call__(
        self,
        authorization: Optional[str] = Header(None),
        x_chorus_instance_id: Optional[str] = Header(
            None, alias="X-Chorus-Instance-Id"
        ),
    ):
        """Performs JWT validation for incoming requests.

        Args:
            authorization: The Authorization header containing the Bearer token.
            x_chorus_instance_id: The X-Chorus-Instance-Id header from the request.

        Raises:
            HTTPException: If authentication fails due to missing headers, invalid token,
                           or replay detection.
        """
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

        token = authorization.split(" ")[1]

        if not self.settings.jwt_public_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="JWT public key not configured on the Bridge.",
            )

        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_public_key,
                algorithms=["EdDSA"],  # Ed25519 is often mapped to EdDSA in JWT
                audience=self.settings.instance_id,  # Validate audience against Bridge's instance ID
                issuer=x_chorus_instance_id,  # Validate issuer against X-Chorus-Instance-Id
                options={
                    "verify_signature": True,
                    "verify_aud": True,
                    "verify_iss": True,
                    "verify_exp": True,  # Validate expiration
                },
            )

            jti = payload.get("jti")
            if jti is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid JWT token: Missing JTI claim",
                )

            # Check for JTI replay protection
            if not self.repository.remember_jti(
                jti, x_chorus_instance_id, int(payload.get("exp", 0))
            ):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid JWT token: JTI replay detected",
                )

        except JOSEError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid JWT token: {e}",
            ) from e


# Global instance of the JWT authenticator
jwt_auth: Optional[JWTAuth] = None
