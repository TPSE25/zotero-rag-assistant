import os
import httpx
from wsgidav.wsgidav_app import WsgiDAVApp
from wsgidav.dir_browser import WsgiDavDirBrowser
from cheroot import wsgi

ROOT_DIR = "/var/lib/webdav/data"
CORE_API_URL = os.getenv("CORE_API_URL")
PORT = 8081

if __name__ == "__main__":
    os.makedirs(ROOT_DIR, exist_ok=True)
    config = {
        "host": "0.0.0.0",
        "port": PORT,
        "provider_mapping": {"/": ROOT_DIR},
        "simple_dc": {"user_mapping": {"*": True}},
        "verbose": 1,
        "dir_browser": {"enable": True},
    }
    app = WsgiDAVApp(config)
    print(f"Serving WebDAV on port {PORT}")
    server = wsgi.Server(("0.0.0.0", PORT), app)
    server.start()
