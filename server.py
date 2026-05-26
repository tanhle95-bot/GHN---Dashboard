import http.server
import socketserver
import sys
import os

# Đảm bảo import được api.data
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from api.data import handler as ApiHandler

PORT = 8080

class DevServerHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # Định tuyến API /api/data về Serverless Function
        if self.path == '/api/data':
            ApiHandler.do_GET(self)
        else:
            # Các đường dẫn khác phục vụ file tĩnh (HTML, CSS, JS)
            super().do_GET()

# Thiết lập để tránh lỗi "Address already in use" khi khởi động lại nhanh
socketserver.TCPServer.allow_reuse_address = True

print(f"===================================================")
print(f" Khởi động Máy chủ Thử nghiệm GHN Dashboard")
print(f" Đường dẫn: http://localhost:{PORT}")
print(f"===================================================")

with socketserver.TCPServer(("", PORT), DevServerHandler) as httpd:
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nĐang tắt máy chủ thử nghiệm...")
