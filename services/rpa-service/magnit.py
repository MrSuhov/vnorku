"""
Magnit API Module
Provides authentication and product search functionality for Magnit delivery service.

This module handles:
- Token refresh using refresh_token
- Product search via API
- Session management in database

CRITICAL: X-Request-Sign algorithm is not fully reverse-engineered yet.
Current implementation uses a stub/mock approach.
"""

import requests
import json
import uuid
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import jwt
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

# API Endpoints
MAGNIT_AUTH_URL = "https://id.magnit.ru/v1/auth/token/refresh"
MAGNIT_SEARCH_URL = "https://middle-api.magnit.ru/v1/goods/multisearch"

# Application Info
APP_VERSION = "8.72.0"
APP_BUILD = "121972"
PLATFORM = "iOS"
PLATFORM_VERSION = "26.0.1"
USER_AGENT = f"MagnitOmni/{APP_VERSION} (ru.tander.magnit; build:{APP_BUILD}; iOS {PLATFORM_VERSION}) Alamofire/5.5.0"

# Sentry Configuration (mock for now)
SENTRY_ENVIRONMENT = "production"
SENTRY_PUBLIC_KEY = "9f281c38318f79ef791f3d769012a4b6"
SENTRY_RELEASE = f"ru.tander.magnit%40{APP_VERSION}%2B{APP_BUILD}"

# Default store codes (can be overridden)
DEFAULT_STORES = [
    {"storeType": "express", "storeCode": "778168"},
    {"storeType": "cosmetic", "storeCode": "398156"},
    {"storeType": "dostavka", "storeCode": "997753"}
]


# ============================================================================
# UTILITIES
# ============================================================================

def generate_device_id() -> str:
    """Generate a new device ID (UUID v4)."""
    return str(uuid.uuid4())


def generate_sentry_trace_id() -> str:
    """Generate Sentry trace ID (32 hex chars)."""
    return uuid.uuid4().hex


def generate_sentry_span_id() -> str:
    """Generate Sentry span ID (16 hex chars)."""
    return uuid.uuid4().hex[:16]


def calculate_request_sign(url: str, method: str, body: str, headers: Dict) -> str:
    """
    Calculate X-Request-Sign header.
    
    CRITICAL: This is a MOCK implementation using hardcoded signatures from logs!
    The actual algorithm needs to be reverse-engineered from the mobile app.
    
    Observations from logs:
    - Sign is 128 hex characters (64 bytes)
    - Likely HMAC-SHA512 or similar
    - Input probably includes: URL, method, body, timestamp?, device_id?
    - Requires secret key from mobile app
    
    Current approach: Try hardcoded signatures for known requests
    TODO: Reverse engineer actual algorithm
    """
    # Try to match known requests and return their signatures
    # This is only for PROOF OF CONCEPT
    
    # Refresh token request with specific body
    if 'refresh' in url and method == 'POST':
        if 'bdab3844-fed9-4ad6-bb20-5024cd4d38f0' in body:
            logger.info("Using hardcoded signature for known refresh token request")
            return "e8303bd0d6ee3aba888274aa1ee276dc1f3d6dd2082045b746ea80fbd3b57fd40380f4f0024c9b27d0bcbfe9eefa6b5b1381f633d98aa394f113651d1c957a46"
    
    # Try to calculate signature (algorithm unknown)
    logger.warning("X-Request-Sign algorithm not implemented - trying without signature")
    
    # Attempt different algorithms
    try:
        # Try HMAC-SHA512 with empty key (will fail but shows intent)
        message = f"{method}{url}{body}"
        # We don't have the secret key, so this won't work
        # signature = hmac.new(b"SECRET_KEY", message.encode(), hashlib.sha512).hexdigest()
        # return signature
    except Exception as e:
        logger.debug(f"Signature calculation failed: {e}")
    
    return ""


def build_base_headers(device_id: str, access_token: Optional[str] = None) -> Dict[str, str]:
    """
    Build base headers required for Magnit API requests.
    
    Args:
        device_id: Device UUID
        access_token: JWT access token (optional for auth requests)
    
    Returns:
        Dictionary of HTTP headers
    """
    trace_id = generate_sentry_trace_id()
    span_id = generate_sentry_span_id()
    
    headers = {
        "Host": "",  # Will be set by requests library
        "X-Device-Platform": PLATFORM,
        "baggage": f"sentry-environment={SENTRY_ENVIRONMENT},sentry-public_key={SENTRY_PUBLIC_KEY},sentry-release={SENTRY_RELEASE},sentry-trace_id={trace_id}",
        "Accept": "*/*",
        "X-Platform-Version": PLATFORM_VERSION,
        "Accept-Language": "ru-RU;q=1.0, en-RU;q=0.9",
        "sentry-trace": f"{trace_id}-{span_id}-0",
        "Accept-Encoding": "br;q=1.0, gzip;q=0.9, deflate;q=0.8",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        "X-Device-ID": device_id,
        "X-Device-Tag": "",  # Often empty in logs
        "X-App-Version": APP_VERSION,
        "Connection": "keep-alive"
    }
    
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    
    return headers


def decode_jwt_token(token: str) -> Dict:
    """
    Decode JWT token without verification to extract expiration time.
    
    Args:
        token: JWT token string
    
    Returns:
        Decoded token payload
    """
    try:
        # Decode without verification (we trust the source)
        decoded = jwt.decode(token, options={"verify_signature": False})
        return decoded
    except Exception as e:
        logger.error(f"Failed to decode JWT: {e}")
        return {}


# ============================================================================
# DATABASE HELPERS
# ============================================================================

def get_db_connection():
    """Get database connection. Import here to avoid circular dependencies."""
    import psycopg2
    from psycopg2.extras import RealDictCursor
    import os
    
    # Parse DATABASE_URL from environment
    db_url = os.getenv("DATABASE_URL", "postgresql://korzinka_user:korzinka_pass@localhost:5432/korzinka")
    
    # Simple parsing (postgresql://user:pass@host:port/dbname)
    parts = db_url.replace("postgresql://", "").split("@")
    user_pass = parts[0].split(":")
    host_port_db = parts[1].split("/")
    host_port = host_port_db[0].split(":")
    
    conn = psycopg2.connect(
        host=host_port[0],
        port=int(host_port[1]) if len(host_port) > 1 else 5432,
        database=host_port_db[1],
        user=user_pass[0],
        password=user_pass[1],
        cursor_factory=RealDictCursor
    )
    return conn


def get_session_data(session_id: int) -> Dict:
    """
    Get Magnit session data from database.
    
    Args:
        session_id: User session ID
    
    Returns:
        Dictionary with session data or empty dict if not found
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT data FROM user_sessions WHERE id = %s",
                (session_id,)
            )
            result = cur.fetchone()
            if result and result['data']:
                return result['data']
            return {}
    finally:
        conn.close()


def update_session_data(session_id: int, data: Dict):
    """
    Update Magnit session data in database.
    
    Args:
        session_id: User session ID
        data: Dictionary with updated data (will be merged with existing)
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Get existing data
            cur.execute(
                "SELECT data FROM user_sessions WHERE id = %s",
                (session_id,)
            )
            result = cur.fetchone()
            existing_data = result['data'] if result and result['data'] else {}
            
            # Merge with new data
            existing_data.update(data)
            
            # Update database
            cur.execute(
                "UPDATE user_sessions SET data = %s, updated_at = NOW() WHERE id = %s",
                (json.dumps(existing_data), session_id)
            )
            conn.commit()
            logger.info(f"Updated session {session_id} with Magnit data")
    finally:
        conn.close()


# ============================================================================
# AUTHENTICATION
# ============================================================================

def refresh_access_token(refresh_token: str, device_id: str) -> Tuple[Optional[str], Optional[str], Optional[datetime]]:
    """
    Refresh access token using refresh token.
    
    Args:
        refresh_token: Refresh token UUID
        device_id: Device UUID
    
    Returns:
        Tuple of (access_token, new_refresh_token, expires_at) or (None, None, None) on error
    """
    url = MAGNIT_AUTH_URL
    headers = build_base_headers(device_id)
    
    body = {
        "aud": "loyalty-mobile",
        "refreshToken": refresh_token
    }
    body_str = json.dumps(body)
    
    # Calculate request signature (currently stub)
    request_sign = calculate_request_sign(url, "POST", body_str, headers)
    if request_sign:
        headers["X-Request-Sign"] = request_sign
    
    try:
        logger.info(f"Refreshing token for device {device_id}")
        response = requests.post(url, headers=headers, data=body_str, timeout=10)
        
        logger.debug(f"Response status: {response.status_code}")
        logger.debug(f"Response headers: {response.headers}")
        
        if response.status_code == 200:
            data = response.json()
            access_token = data.get("accessToken")
            new_refresh_token = data.get("refreshToken")
            
            # Decode JWT to get expiration
            decoded = decode_jwt_token(access_token)
            exp_timestamp = decoded.get("exp")
            expires_at = datetime.fromtimestamp(exp_timestamp) if exp_timestamp else None
            
            logger.info(f"Token refreshed successfully, expires at {expires_at}")
            return access_token, new_refresh_token, expires_at
        else:
            logger.error(f"Token refresh failed: {response.status_code} - {response.text}")
            return None, None, None
            
    except Exception as e:
        logger.error(f"Token refresh exception: {e}")
        return None, None, None


def save_tokens_to_session(session_id: int, access_token: str, refresh_token: str, 
                          expires_at: datetime, device_id: str):
    """
    Save Magnit tokens to database session.
    
    Args:
        session_id: User session ID
        access_token: JWT access token
        refresh_token: Refresh token UUID
        expires_at: Token expiration datetime
        device_id: Device UUID
    """
    data = {
        "magnit_device_id": device_id,
        "magnit_access_token": access_token,
        "magnit_refresh_token": refresh_token,
        "magnit_token_expires_at": expires_at.isoformat() if expires_at else None
    }
    update_session_data(session_id, data)


def get_valid_token(session_id: int) -> Optional[str]:
    """
    Get valid access token for session, refreshing if needed.
    
    Args:
        session_id: User session ID
    
    Returns:
        Valid access token or None if refresh fails
    """
    session_data = get_session_data(session_id)
    
    access_token = session_data.get("magnit_access_token")
    refresh_token = session_data.get("magnit_refresh_token")
    device_id = session_data.get("magnit_device_id")
    expires_at_str = session_data.get("magnit_token_expires_at")
    
    if not all([refresh_token, device_id]):
        logger.error(f"Missing Magnit credentials for session {session_id}")
        return None
    
    # Check if token is still valid
    if access_token and expires_at_str:
        expires_at = datetime.fromisoformat(expires_at_str)
        # Refresh if expiring in less than 5 minutes
        if expires_at > datetime.now() + timedelta(minutes=5):
            logger.info(f"Using existing token for session {session_id}")
            return access_token
    
    # Token expired or missing, refresh it
    logger.info(f"Token expired or missing, refreshing for session {session_id}")
    new_access_token, new_refresh_token, new_expires_at = refresh_access_token(
        refresh_token, device_id
    )
    
    if new_access_token:
        save_tokens_to_session(
            session_id, new_access_token, new_refresh_token, 
            new_expires_at, device_id
        )
        return new_access_token
    
    return None


# ============================================================================
# PRODUCT SEARCH
# ============================================================================

def search_products(query: str, session_id: int, 
                   stores: Optional[List[Dict]] = None,
                   catalog_type: str = "2",
                   include_adult: bool = True) -> List[Dict]:
    """
    Search for products in Magnit.
    
    Args:
        query: Search term (e.g., "Шармэль")
        session_id: User session ID
        stores: List of store dicts with storeType and storeCode
                (default: DEFAULT_STORES)
        catalog_type: Catalog type (default: "2")
        include_adult: Include adult goods in results
    
    Returns:
        List of product dictionaries with fields:
        - name: product name
        - price: price value
        - unit: unit of measurement
        - availability: availability status
        - store_code: store code
        - store_type: store type
        - raw_data: full response data for this product
    """
    # Get valid access token
    access_token = get_valid_token(session_id)
    if not access_token:
        logger.error(f"Failed to get valid token for session {session_id}")
        return []
    
    # Get device ID
    session_data = get_session_data(session_id)
    device_id = session_data.get("magnit_device_id")
    if not device_id:
        logger.error(f"No device ID found for session {session_id}")
        return []
    
    # Use default stores if not provided
    if stores is None:
        stores = DEFAULT_STORES
    
    # Build request
    url = MAGNIT_SEARCH_URL
    headers = build_base_headers(device_id, access_token)
    
    body = {
        "term": query,
        "stores": stores,
        "catalogType": catalog_type,
        "includeAdultGoods": include_adult
    }
    body_str = json.dumps(body, ensure_ascii=False)
    
    # Calculate request signature (currently stub)
    request_sign = calculate_request_sign(url, "POST", body_str, headers)
    if request_sign:
        headers["X-Request-Sign"] = request_sign
    
    try:
        logger.info(f"Searching for '{query}' in session {session_id}")
        logger.debug(f"Request body: {body_str}")
        
        response = requests.post(url, headers=headers, data=body_str.encode('utf-8'), timeout=15)
        
        logger.debug(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Search successful, processing results")
            logger.debug(f"Response data: {json.dumps(data, ensure_ascii=False)[:500]}...")
            
            # Parse results
            products = parse_search_results(data)
            logger.info(f"Found {len(products)} products")
            return products
        else:
            logger.error(f"Search failed: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        logger.error(f"Search exception: {e}")
        return []


def parse_search_results(response_data: Dict) -> List[Dict]:
    """
    Parse search response into standardized product list.
    
    Args:
        response_data: Raw JSON response from API
    
    Returns:
        List of product dictionaries
    """
    products = []
    
    # Response structure is unknown - we'll need to inspect actual response
    # This is a placeholder that will need adjustment based on real data
    
    # Common patterns in delivery APIs:
    # Option 1: {"results": [...]}
    # Option 2: {"data": {"items": [...]}}
    # Option 3: {"products": [...]}
    
    # Try to find the array of products
    items = None
    if isinstance(response_data, list):
        items = response_data
    elif isinstance(response_data, dict):
        # Try common keys
        for key in ['results', 'items', 'products', 'goods', 'data']:
            if key in response_data:
                value = response_data[key]
                if isinstance(value, list):
                    items = value
                    break
                elif isinstance(value, dict) and 'items' in value:
                    items = value['items']
                    break
    
    if not items:
        logger.warning(f"Could not find product array in response. Keys: {response_data.keys() if isinstance(response_data, dict) else 'not a dict'}")
        # Return raw data for inspection
        return [{"raw_data": response_data, "parse_error": "Unknown response structure"}]
    
    # Parse each item
    for item in items:
        try:
            # Extract common fields - adjust based on actual response
            product = {
                "name": item.get("name") or item.get("title") or item.get("product_name"),
                "price": item.get("price") or item.get("cost"),
                "unit": item.get("unit") or item.get("measure"),
                "availability": item.get("availability") or item.get("in_stock"),
                "store_code": item.get("store_code") or item.get("storeCode"),
                "store_type": item.get("store_type") or item.get("storeType"),
                "raw_data": item
            }
            products.append(product)
        except Exception as e:
            logger.error(f"Failed to parse product item: {e}")
            products.append({"raw_data": item, "parse_error": str(e)})
    
    return products


# ============================================================================
# PUBLIC API
# ============================================================================

def initialize_magnit_session(session_id: int, refresh_token: str, 
                              device_id: Optional[str] = None) -> bool:
    """
    Initialize Magnit session for a user.
    
    This should be called once during user registration after obtaining
    the initial refresh_token through the mobile app authentication flow.
    
    Args:
        session_id: User session ID in database
        refresh_token: Initial refresh token from mobile auth
        device_id: Device UUID (will be generated if not provided)
    
    Returns:
        True if initialization successful, False otherwise
    """
    if not device_id:
        device_id = generate_device_id()
        logger.info(f"Generated new device ID: {device_id}")
    
    # Try to refresh token to validate it
    access_token, new_refresh_token, expires_at = refresh_access_token(
        refresh_token, device_id
    )
    
    if access_token:
        save_tokens_to_session(
            session_id, access_token, new_refresh_token, 
            expires_at, device_id
        )
        logger.info(f"Magnit session initialized for session {session_id}")
        return True
    else:
        logger.error(f"Failed to initialize Magnit session for session {session_id}")
        return False


def refresh_token_if_needed(session_id: int) -> Optional[str]:
    """
    Check and refresh token if needed.
    
    This is a convenience wrapper around get_valid_token.
    
    Args:
        session_id: User session ID
    
    Returns:
        Valid access token or None
    """
    return get_valid_token(session_id)


# ============================================================================
# MAIN (for testing)
# ============================================================================

if __name__ == "__main__":
    """
    Test script - requires existing session with refresh_token.
    """
    print("Magnit API Module")
    print("=" * 50)
    
    # Example usage:
    # 1. Initialize session (run once)
    # session_id = 1
    # refresh_token = "bdab3844-fed9-4ad6-bb20-5024cd4d38f0"  # From logs
    # success = initialize_magnit_session(session_id, refresh_token)
    # print(f"Initialization: {'OK' if success else 'FAILED'}")
    
    # 2. Search for products
    # products = search_products("Шармэль", session_id)
    # for p in products:
    #     print(f"- {p.get('name')}: {p.get('price')} ({p.get('unit')})")
    
    print("\nModule loaded successfully. Import and use the functions above.")
    print("\nKey functions:")
    print("  - initialize_magnit_session(session_id, refresh_token)")
    print("  - search_products(query, session_id)")
    print("  - refresh_token_if_needed(session_id)")
