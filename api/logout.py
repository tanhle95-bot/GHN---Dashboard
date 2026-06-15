from http.server import BaseHTTPRequestHandler
import json
from api.auth_middleware import get_logout_cookie


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Set-Cookie', get_logout_cookie())
        self.end_headers()
        self.wfile.write(json.dumps({'ok': True}).encode('utf-8'))

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Set-Cookie', get_logout_cookie())
        self.end_headers()
        self.wfile.write(json.dumps({'ok': True}).encode('utf-8'))
