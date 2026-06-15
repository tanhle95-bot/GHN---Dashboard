from http.server import BaseHTTPRequestHandler
from api.auth_middleware import check_auth, send_json, send_unauthorized


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        username = check_auth(self)
        if not username:
            send_unauthorized(self)
            return
        send_json(self, 200, {'authenticated': True, 'username': username})
