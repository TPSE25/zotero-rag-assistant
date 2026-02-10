import logging
import os
import httpx
import sys
import signal
from wsgidav.wsgidav_app import WsgiDAVApp
from wsgidav.dir_browser import WsgiDavDirBrowser
from cheroot import wsgi

ROOT_DIR = os.getenv("ROOT_DIR")
CORE_API_URL = os.getenv("CORE_API_URL")
PORT = int(os.getenv("PORT"))

logging.basicConfig(
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)],
)

class NotificationMiddleware:
    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):
        method = environ.get("REQUEST_METHOD")
        path_info = environ.get("PATH_INFO", "")
        def custom_start_response(status, response_headers, exc_info=None):
            if method not in ["GET", "HEAD", "OPTIONS", "LOCK", "UNLOCK", "PROPFIND"]:
                self._notify_core(method, path_info)
            return start_response(status, response_headers, exc_info)

        return self.application(environ, custom_start_response)

    def _notify_core(self, method, filename):
        clean_filename = filename.lstrip("/")
        full_path = os.path.join(ROOT_DIR, clean_filename)
        print(f"[{method}] {clean_filename} - Sending hook...")
        try:
            with httpx.Client() as client:
                with open(full_path, "rb") as f:
                    client.post(
                        CORE_API_URL,
                        data={
                            "filename": clean_filename,
                            "event_type": method
                        },
                        files={"file": (clean_filename, f)},
                        timeout=5.0,
                    )
        except Exception as e:
            print(f"Error notifying core: {e}", flush=True)


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
    app = NotificationMiddleware(WsgiDAVApp(config))
    print(f"Serving WebDAV on port {PORT}")
    server = wsgi.Server(("0.0.0.0", PORT), app)

    signal.signal(signal.SIGTERM, lambda sig, frame: server.stop())
    signal.signal(signal.SIGINT, lambda sig, frame: server.stop())

    server.start()
