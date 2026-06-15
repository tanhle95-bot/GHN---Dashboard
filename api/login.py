from http.server import BaseHTTPRequestHandler
import json
import hashlib
import os
import time
from api.auth_middleware import create_token, get_session_cookie, send_json, validate_origin

# Simple in-memory rate limiting for login attempts
login_attempts = {}
MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 900  # 15 minutes


def hash_password(password, salt):
    """Hash password with SHA-256 + salt (simple, no external deps)"""
    return hashlib.sha256(f'{salt}{password}'.encode()).hexdigest()


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # CSRF origin validation
        if not validate_origin(self):
            send_json(self, 403, {'error': 'Forbidden'})
            return

        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))
        except (json.JSONDecodeError, ValueError):
            send_json(self, 400, {'error': 'Invalid request'})
            return

        username = data.get('username', '').strip()
        password = data.get('password', '').strip()

        if not username or not password:
            send_json(self, 400, {'error': 'Vui lòng nhập tên đăng nhập và mật khẩu'})
            return

        # Rate limiting check
        client_ip = self.headers.get('X-Forwarded-For', '').split(',')[0].strip() or 'unknown'
        rate_key = f'{client_ip}:{username}'
        now = time.time()

        if rate_key in login_attempts:
            record = login_attempts[rate_key]
            if record['count'] >= MAX_ATTEMPTS and now < record['locked_until']:
                retry_after = int(record['locked_until'] - now)
                self.send_response(429)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Retry-After', str(retry_after))
                self.end_headers()
                self.wfile.write(json.dumps({
                    'error': 'Tài khoản tạm thời bị khóa do đăng nhập sai quá nhiều lần. Vui lòng thử lại sau.'
                }).encode('utf-8'))
                return

        # Verify credentials from environment
        # Format: USERS=admin:salt:hash,user2:salt2:hash2
        default_hash = hash_password('GHN@2024secure', 'ghn2024salt')
        users_str = os.environ.get('USERS', f'admin:ghn2024salt:{default_hash}')
        users = {}
        for entry in users_str.split(','):
            parts = entry.strip().split(':')
            if len(parts) == 3:
                users[parts[0]] = {'salt': parts[1], 'hash': parts[2]}

        user = users.get(username)
        if not user or hash_password(password, user['salt']) != user['hash']:
            # Record failed attempt
            if rate_key not in login_attempts:
                login_attempts[rate_key] = {'count': 0, 'locked_until': 0}
            login_attempts[rate_key]['count'] += 1
            if login_attempts[rate_key]['count'] >= MAX_ATTEMPTS:
                login_attempts[rate_key]['locked_until'] = now + LOCKOUT_SECONDS
            send_json(self, 401, {'error': 'Sai tên đăng nhập hoặc mật khẩu'})
            return

        # Clear failed attempts on success
        if rate_key in login_attempts:
            del login_attempts[rate_key]

        # Create session token
        token = create_token(username)

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Set-Cookie', get_session_cookie(token))
        self.end_headers()
        self.wfile.write(json.dumps({'ok': True, 'username': username}).encode('utf-8'))

    def do_GET(self):
        send_json(self, 405, {'error': 'Method not allowed'})
