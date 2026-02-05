import http.server
import socketserver
import os

PORT = 3000
DIRECTORY = "/app/frontend/dist"

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
    
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

    def do_GET(self):
        # Serve index.html for SPA routes
        if not os.path.exists(os.path.join(DIRECTORY, self.path.lstrip('/'))):
            if not self.path.startswith('/_expo') and not self.path.startswith('/assets'):
                self.path = '/index.html'
        return super().do_GET()

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Serving at port {PORT}")
    httpd.serve_forever()
