import http.server
import socketserver
import webbrowser

PORT = 8080
Handler = http.server.SimpleHTTPRequestHandler

print("="*50)
print(f" Starting local server at http://localhost:{PORT}")
print(" Open this link in your browser if it didn't open automatically.")
print(" Press Ctrl+C in terminal to stop.")
print("="*50)

# Automatically open the browser
webbrowser.open(f"http://localhost:{PORT}")

try:
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()
except KeyboardInterrupt:
    print("\nServer stopped. Have a good day!")
