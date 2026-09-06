"""The console: one page, on his own machine, reading his own database.

Everything the search knows already lives in data/local/postings.db, including
the eight and a half thousand posting bodies. Until this existed, seeing any of
it meant running a command that wrote a file, opening the file, and finding it
a day stale by the next poll, so half the search lived on disk and half lived in
a chat window and neither half was the whole thing. This serves the same page
the digest writes, from the store, live, and adds the two things a file cannot
do: a posting's state goes back to the database when he clicks, and the letter
brief is written on demand for the posting he is looking at.

Local only. It binds 127.0.0.1 because the store holds his search and there is
no version of this that belongs on a network. Stdlib only, per ADR-0004, so it
starts with the same python the scheduled tasks use and there is nothing to
install before it runs.
"""

import json
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

from . import companies as companies_mod, digest_html
from .score import load_rules
from .store import STATES, Store

ROOT = Path(__file__).resolve().parent.parent
HOST, PORT = "127.0.0.1", 4319


def _json(handler, code, payload):
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _html(handler, code, text):
    body = text.encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    # The store is his search. Nothing here is cached anywhere but memory.
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


class Console:
    """Holds the paths and opens a store per request.

    A connection per request rather than one held open, because the nightly
    poll writes to the same file and a long-lived reader is how a scheduled job
    starts failing at four in the morning for reasons nobody is awake to see.
    """

    def __init__(self, db, companies_path, letters_dir):
        self.db = db
        self.companies_path = companies_path
        self.letters_dir = Path(letters_dir)
        self.rules = load_rules()

    def companies(self):
        data = companies_mod.load(self.companies_path)
        return {c["slug"]: c for c in data["companies"]}

    def page(self):
        store = Store(self.db)
        try:
            return digest_html.render(store, self.rules, self.companies(),
                                      datetime.now(timezone.utc), live=True)
        finally:
            store.close()

    def mark(self, posting_id, state):
        if state not in STATES:
            raise ValueError(f"unknown state {state!r}")
        store = Store(self.db)
        try:
            store.mark(posting_id, state)
            return store.state_of(posting_id)
        finally:
            store.close()

    def brief(self, posting_id):
        """The brief for one posting, written and returned. Same code the CLI
        runs, so there is one generator and the console cannot drift from it."""
        from letters import assemble
        from letters.voicelint import load_rules as load_voice
        store = Store(self.db)
        try:
            posting = store.get(posting_id)
        finally:
            store.close()
        if posting is None:
            raise KeyError(posting_id)
        cos = self.companies()
        company = cos.get(posting["company_slug"]) or {
            "slug": posting["company_slug"], "name": posting["company_slug"],
            "category": None, "priority": None,
        }
        chosen = assemble.select(posting, company)
        md = assemble.render_brief(posting, company, chosen, load_voice())
        out_dir = self.letters_dir / "briefs"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{company['slug']}-{posting_id}.md"
        path.write_text(md, encoding="utf-8")
        return md, path

    def resume(self):
        from letters import page as page_mod
        record = json.loads((ROOT / "data" / "resume.json").read_text(encoding="utf-8"))
        skills = json.loads((ROOT / "data" / "skills.json").read_text(encoding="utf-8"))["skills"]
        return page_mod.resume(record, skills)


def handler_for(console):
    class Handler(BaseHTTPRequestHandler):
        server_version = "jobhunt-console"

        def log_message(self, fmt, *args):
            pass  # the terminal is for the two lines that say where it is

        def do_GET(self):
            path = urlparse(self.path).path
            try:
                if path == "/":
                    return _html(self, 200, console.page())
                if path == "/resume":
                    return _html(self, 200, console.resume())
                if path == "/favicon.ico":
                    # Asked for by every browser on every load. Answering it
                    # keeps a 404 out of the console every time he opens a tab.
                    self.send_response(204)
                    self.end_headers()
                    return
            except Exception as e:  # a broken page is a message, not a stack trace
                return _html(self, 500, f"<pre>{type(e).__name__}: {e}</pre>")
            self.send_error(404)

        def do_POST(self):
            path = urlparse(self.path).path
            length = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                return _json(self, 400, {"error": "bad json"})
            try:
                if path == "/api/mark":
                    state = console.mark(int(body["id"]), body["state"])
                    return _json(self, 200, {"id": body["id"], "state": state})
                if path == "/api/brief":
                    md, where = console.brief(int(body["id"]))
                    return _json(self, 200, {"brief": md, "path": str(where)})
            except KeyError:
                return _json(self, 404, {"error": "no such posting"})
            except (ValueError, TypeError) as e:
                return _json(self, 400, {"error": str(e)})
            except Exception as e:
                return _json(self, 500, {"error": f"{type(e).__name__}: {e}"})
            self.send_error(404)

    return Handler


def serve(db, companies_path, letters_dir, port=PORT, open_browser=True):
    console = Console(db, companies_path, letters_dir)
    httpd = HTTPServer((HOST, port), handler_for(console))
    url = f"http://{HOST}:{port}/"
    print(f"\n  the console     {url}")
    print(f"  the resume      {url}resume\n")
    print("  Everything is live off the store. Ctrl-C stops it.\n")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
    return 0
