"""
SentinelAI Authentication Module
Google OAuth + JWT Token Authentication
"""

import os
import jwt
import httpx
from datetime import datetime, timedelta
from typing import Optional, Dict
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

# ============================================================================
# CONFIGURATION
# ============================================================================
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
JWT_SECRET = os.getenv("JWT_SECRET", "change_me_in_production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Google OAuth URLs
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# ============================================================================
# MODELS
# ============================================================================
class User(BaseModel):
    id: str
    email: str
    name: str
    picture: Optional[str] = None
    role: str = "user"

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: User

# ============================================================================
# JWT UTILITIES
# ============================================================================
def create_jwt_token(user: User) -> str:
    """Create a JWT token for the user."""
    payload = {
        "sub": user.id,
        "email": user.email,
        "name": user.name,
        "picture": user.picture,
        "role": user.role,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_jwt_token(token: str) -> Optional[Dict]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ============================================================================
# GOOGLE OAUTH
# ============================================================================
def get_google_auth_url(state: Optional[str] = None) -> str:
    """Generate Google OAuth authorization URL."""
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    if state:
        params["state"] = state
    
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GOOGLE_AUTH_URL}?{query}"

async def exchange_code_for_tokens(code: str) -> Dict:
    """Exchange authorization code for tokens."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": GOOGLE_REDIRECT_URI,
            },
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to exchange code: {response.text}"
            )
        
        return response.json()

async def get_google_user_info(access_token: str) -> Dict:
    """Get user info from Google using access token."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail="Failed to get user info from Google"
            )
        
        return response.json()

# ============================================================================
# AUTH DEPENDENCY
# ============================================================================
security = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[User]:
    """Get current user from JWT token (optional - returns None if no token)."""
    if not credentials:
        return None
    
    payload = decode_jwt_token(credentials.credentials)
    return User(
        id=payload["sub"],
        email=payload["email"],
        name=payload["name"],
        picture=payload.get("picture"),
        role=payload.get("role", "user"),
    )

async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())
) -> User:
    """Require authentication - raises 401 if no valid token."""
    payload = decode_jwt_token(credentials.credentials)
    return User(
        id=payload["sub"],
        email=payload["email"],
        name=payload["name"],
        picture=payload.get("picture"),
        role=payload.get("role", "user"),
    )

# ============================================================================
# IN-MEMORY USER STORE (Replace with database in production)
# ============================================================================
users_store: Dict[str, User] = {}

def get_or_create_user(google_user: Dict) -> User:
    """Get existing user or create new one from Google user info."""
    user_id = google_user["id"]
    
    if user_id in users_store:
        # Update user info
        users_store[user_id].name = google_user.get("name", "")
        users_store[user_id].picture = google_user.get("picture")
        return users_store[user_id]
    
    # Create new user
    user = User(
        id=user_id,
        email=google_user["email"],
        name=google_user.get("name", google_user["email"].split("@")[0]),
        picture=google_user.get("picture"),
        role="admin" if len(users_store) == 0 else "user",  # First user is admin
    )
    users_store[user_id] = user
    return user
