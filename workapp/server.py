import argparse
import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from .domain import validate_filters
from .service import Service

STATIC = Path(__file__).parent / "static"


def make_handler(service):
    class Handler(BaseHTTPRequestHandler):
        def send_json(self, data, status=200):
            body = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            try:
                if parsed.path == "/api/jobs":
                    filters = validate_filters(query)
                    statuses = service.refresh()
                    jobs = service.jobs(filters)
                    page = max(1, int(query.get("page", 1)))
                    self.send_json({"jobs": jobs[(page - 1) * 30:page * 30], "total": len(jobs), "page": page, "sources": statuses})
                elif parsed.path == "/api/rules":
                    self.send_json({"rules": service.rules()})
                elif parsed.path == "/api/discoveries":
                    self.send_json({"jobs": service.discoveries(int(query["rule_id"]))})
                elif parsed.path == "/api/status":
                    self.send_json({"sources": service.source_status(), "scheduler": "running"})
                else:
                    filename = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css", "/favicon.svg": "favicon.svg"}.get(parsed.path)
                    if not filename:
                        return self.send_json({"error": "找不到頁面"}, 404)
                    body = (STATIC / filename).read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", {"html": "text/html; charset=utf-8", "js": "application/javascript; charset=utf-8", "css": "text/css; charset=utf-8", "svg": "image/svg+xml"}[filename.split(".")[-1]])
                    self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
            except (ValueError, KeyError, TypeError) as exc:
                self.send_json({"error": str(exc)}, 400)
            except Exception:
                logging.exception("GET failed")
                self.send_json({"error": "服務暫時無法讀取資料，請稍後再試"}, 500)

        def do_POST(self):
            # Local personal app: disallow cross-origin writes and non-JSON forms.
            origin = self.headers.get("Origin")
            if (origin and urlparse(origin).netloc != self.headers.get("Host")) or not self.headers.get("Content-Type", "").startswith("application/json"):
                return self.send_json({"error": "請從 WorkApp 網頁操作"}, 403)
            try:
                length = int(self.headers.get("Content-Length", 0))
                if not 0 < length <= 16384:
                    raise ValueError("請求大小不正確")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError("請求格式不正確")
                path = urlparse(self.path).path
                if path == "/api/search":
                    jobs, statuses = service.search_all(validate_filters(data))
                    page = max(1, int(data.get('page', 1)))
                    self.send_json({'jobs':jobs[(page-1)*30:page*30],'total':len(jobs),'page':page,'sources':statuses})
                elif path == "/api/search104":
                    self.send_json(service.search104.search(validate_filters(data)))
                elif path == "/api/web-search":
                    self.send_json(service.web_search.search(validate_filters(data)))
                elif path == "/api/rules":
                    self.send_json({"id": service.add_rule(data)}, 201)
                elif path == "/api/scan":
                    self.send_json(service.scan(int(data["id"])))
                elif path == "/api/rules/pause":
                    service.update_rule(int(data["id"]), data["paused"])
                    self.send_json({"ok": True})
                elif path == "/api/rules/delete":
                    service.delete_rule(int(data["id"]))
                    self.send_json({"ok": True})
                else:
                    self.send_json({"error": "找不到操作"}, 404)
            except (ValueError, KeyError, TypeError) as exc:
                self.send_json({"error": str(exc)}, 400)
            except Exception:
                logging.exception("POST failed")
                self.send_json({"error": "操作未完成，請稍後再試"}, 500)
    return Handler


def main():
    parser = argparse.ArgumentParser(description="WorkApp personal job monitor")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--database", default="data/workapp.sqlite3")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    service = Service(args.database)
    service.start()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(service))
    print(f"WorkApp: http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        service.stop.set()
        server.server_close()


if __name__ == "__main__":
    main()
