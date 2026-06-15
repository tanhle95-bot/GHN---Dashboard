import os
import json
import hashlib
import hmac
import time
import base64

JWT_SECRET = os.environ.get('JWT_SECRET', 'change-this-in-production-abc123xyz')
SESSION_MAX_AGE = 8 * 60 * 60  # 8 hours


def create_token(username):
    """Create a simple signed token (JWT-like, no external deps)"""
    header = base64.urlsafe_b64encode(json.dumps({'alg': 'HS256', 'typ': 'JWT'}).encode()).decode().rstrip('=')
    payload = base64.urlsafe_b64encode(json.dumps({
        'sub': username,
        'iat': int(time.time()),
        'exp': int(time.time()) + SESSION_MAX_AGE
    }).encode()).decode().rstrip('=')

    signature = hmac.new(
        JWT_SECRET.encode(),
        f'{header}.{payload}'.encode(),
        hashlib.sha256
    ).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).decode().rstrip('=')
    return f'{header}.{payload}.{sig_b64}'


def verify_token(token):
    """Verify token and return username or None"""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None

        header, payload, signature = parts

        # Verify signature
        expected_sig = hmac.new(
            JWT_SECRET.encode(),
            f'{header}.{payload}'.encode(),
            hashlib.sha256
        ).digest()
        expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).decode().rstrip('=')

        if not hmac.compare_digest(signature, expected_sig_b64):
            return None

        # Decode payload
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += '=' * padding
        payload_data = json.loads(base64.urlsafe_b64decode(payload).decode())

        # Check expiration
        if payload_data.get('exp', 0) < time.time():
            return None

        return payload_data.get('sub')
    except Exception:
        return None


def get_session_cookie(token):
    """Generate Set-Cookie header value with security flags"""
    return f'session_token={token}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age={SESSION_MAX_AGE}'


def get_logout_cookie():
    """Generate Set-Cookie header to clear session"""
    return 'session_token=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0'


def check_auth(handler):
    """Check if request has valid session cookie. Returns username or None."""
    cookie_header = handler.headers.get('Cookie', '')
    cookies = {}
    for item in cookie_header.split(';'):
        item = item.strip()
        if '=' in item:
            key, val = item.split('=', 1)
            cookies[key.strip()] = val.strip()

    token = cookies.get('session_token')
    if not token:
        return None
    return verify_token(token)


def send_json(handler, status, data):
    """Send JSON response with proper headers"""
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json')
    handler.end_headers()
    handler.wfile.write(json.dumps(data).encode('utf-8'))


def send_unauthorized(handler):
    """Send 401 response"""
    send_json(handler, 401, {'error': 'Authentication required'})


def validate_origin(handler):
    """Validate Origin header for CSRF prevention. Returns True if valid."""
    origin = handler.headers.get('Origin', '')
    referer = handler.headers.get('Referer', '')

    allowed_origins = os.environ.get('ALLOWED_ORIGINS', 'https://ghn-dashboard-j6vc.vercel.app').split(',')
    # Also allow same-origin requests (no Origin header)
    if not origin and not referer:
        return True

    for allowed in allowed_origins:
        allowed = allowed.strip()
        if origin.startswith(allowed) or referer.startswith(allowed):
            return True

    return False
