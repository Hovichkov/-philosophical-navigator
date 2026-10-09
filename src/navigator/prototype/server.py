"""Local browser prototype (M3). Standard-library HTTP server + one static page.

Routes
  GET  /                      the app (static/index.html)
  GET  /api/options           topics, experiences, difficulty options per topic
  POST /api/interpret         {topic, experiences, difficulty_center, narrative} → proposed question / clarification
  POST /api/confirm           {session_id, action, text?} → confirmed question
  POST /api/retrieve          {session_id} → stage 1: candidate retrieval (fast, local)
  POST /api/compose           {session_id} → stage 2: 2–3 perspectives (one model call)
  POST /api/answer            {session_id} → both stages in one request
  POST /api/reflect           {session_id, chosen?, text?} → M3.4: the thought the person continues with
  GET  /debug                 developer view: sessions list (not linked from the app)
  GET  /debug/session/<id>    full internal trace (JSON)

Local only: binds to 127.0.0.1. No accounts, database, analytics or cloud.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import os
import shutil
import sys
import threading
import traceback
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from navigator.prototype.flow import USER_ERROR, FlowError, Services, Session
from navigator.prototype.options import DIFFICULTY_OPTIONS, EXPERIENCES, TOPICS, difficulty_options

STATIC = Path(__file__).parent / "static"
MAX_BODY = 64 * 1024


def ensure_claude_on_path() -> str | None:
    """The composer/interpreter call `claude`; make sure a GUI-launched server can find it."""
    if shutil.which("claude"):
        return shutil.which("claude")
    for d in ("/usr/local/bin", "/opt/homebrew/bin", str(Path.home() / ".local/bin"), str(Path.home() / ".claude/local")):
        if (Path(d) / "claude").exists():
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
            return str(Path(d) / "claude")
    return None


class App:
    def __init__(self, services: Services, trace_dir: Path | None):
        self.services = services
        self.trace_dir = trace_dir
        self.sessions: dict[str, Session] = {}
        self.lock = threading.Lock()

    def new_session(self) -> Session:
        s = Session(self.services, self.trace_dir)
        with self.lock:
            self.sessions[s.id] = s
        return s

    def log_error(self, path: str, tb: str) -> None:
        """MVP stabilization: an unexpected server error is printed and appended to <trace_dir>/_server-errors.log."""
        stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        entry = f"--- {stamp} {path}\n{tb}\n"
        print(entry, file=sys.stderr, flush=True)
        if self.trace_dir is not None:
            try:
                self.trace_dir.mkdir(parents=True, exist_ok=True)
                with (self.trace_dir / "_server-errors.log").open("a", encoding="utf-8") as fh:
                    fh.write(entry)
            except OSError:
                pass

    def get(self, sid: str) -> Session:
        with self.lock:
            s = self.sessions.get(sid)
        if s is None:
            raise FlowError("Сессия устарела. Начните заново, пожалуйста.", f"unknown session {sid}")
        return s


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        server_version = "SelfAnalysisPrototype/0.1"

        def log_message(self, fmt, *args):  # keep the console quiet
            pass

        def _send(self, status: int, body: bytes, ctype: str):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, data: dict):
            self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                raise FlowError(USER_ERROR, "request too large")
            raw = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise FlowError(USER_ERROR, "bad json") from exc
            if not isinstance(data, dict):
                raise FlowError(USER_ERROR, "bad json")
            return data

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                return self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            if path == "/api/options":
                return self._json(200, {
                    "topics": TOPICS, "experiences": EXPERIENCES,
                    "difficulty": {t: difficulty_options(t) for t in [*DIFFICULTY_OPTIONS]},
                })
            if path == "/debug":
                return self._send(200, self._debug_index().encode("utf-8"), "text/html; charset=utf-8")
            if path.startswith("/debug/session/"):
                try:
                    return self._json(200, app.get(path.rsplit("/", 1)[-1]).debug_view())
                except FlowError as exc:
                    return self._json(404, {"error": exc.user_message})
            self._send(404, b"Not found", "text/plain; charset=utf-8")

        def do_POST(self):
            path = self.path.split("?", 1)[0]
            try:
                data = self._body()
                if path == "/api/interpret":
                    s = app.new_session()
                    exps = data.get("experiences") or []
                    if not isinstance(exps, list):
                        exps = []
                    return self._json(200, s.submit(str(data.get("topic", "")), [str(e) for e in exps],
                                                    str(data.get("difficulty_center", "")), str(data.get("narrative", ""))))
                if path == "/api/confirm":
                    s = app.get(str(data.get("session_id", "")))
                    return self._json(200, s.confirm(str(data.get("action", "")), data.get("text")))
                if path == "/api/retrieve":
                    return self._json(200, app.get(str(data.get("session_id", ""))).retrieve())
                if path == "/api/compose":
                    return self._json(200, app.get(str(data.get("session_id", ""))).compose())
                if path == "/api/reflect":
                    chosen = data.get("chosen")
                    chosen = chosen if isinstance(chosen, int) and not isinstance(chosen, bool) else None
                    text = data.get("text")
                    return self._json(200, app.get(str(data.get("session_id", ""))).reflect(
                        chosen, str(text) if isinstance(text, str) else None))
                if path == "/api/answer":
                    return self._json(200, app.get(str(data.get("session_id", ""))).answer())
                return self._json(404, {"error": "Not found"})
            except FlowError as exc:
                return self._json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": exc.user_message})
            except Exception:  # never leak a stack trace to the user — but never lose it for the developer
                app.log_error(path, traceback.format_exc())
                return self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": USER_ERROR})

        def _debug_index(self) -> str:
            with app.lock:
                sessions = list(app.sessions.values())
            def label(s):
                if s.confirmation and s.confirmation.confirmed_question:
                    return s.confirmation.confirmed_question
                return s.interpretation.proposed_question if s.interpretation else "—"

            rows = "".join(
                f'<li><a href="/debug/session/{s.id}">{s.id}</a> · {s.created_utc} · {s.state} · {html.escape(label(s))}</li>'
                for s in reversed(sessions)
            )
            return ("<!doctype html><meta charset=utf-8><title>Debug</title>"
                    "<body style='font:14px/1.5 system-ui;margin:2rem;max-width:60rem'>"
                    "<h1>Developer view</h1><p>Internal traces of this server's sessions "
                    f"(also saved to <code>{app.trace_dir}</code>).</p><ol>{rows or '<li>no sessions yet</li>'}</ol>")

    return Handler


CORPORA = {  # corpus name → (fragments, manifest, embedding cache root)
    "compact": ("data/corpus/fragments.jsonl", "data/corpus/launch-manifest.json", "data/retrieval/embeddings"),
    "full": ("data/corpus-full/fragments.jsonl", "data/corpus-full/manifest.json", "data/retrieval/embeddings-full"),
}


FINAL_EMBEDDINGS = "data/retrieval/embeddings-final"
# Candidate pool for the final selection (final corpus). 2026-10-09 multi-view experiment
# (reports/validation/RETRIEVAL-MULTIVIEW-EXPERIMENT.md): 20 beat 15 in the real composer (3 of 7 cases better, none
# worse); multi-view fusion did not win and is not used. 15 = the previous behaviour.
FINAL_POOL_SIZE = 20
POOL_SIZES = (15, 20, 25)


def build_final_services(model: str, mode: str, retrieval_layer: str | None = None,
                         pool_size: int = FINAL_POOL_SIZE) -> Services:
    """Final-corpus TEST mode (not the default runtime): FINAL-CORPUS-ACTIVE-v1.csv through the contract validator,
    retrieval documents of experimental mode A / B / C, verified quotes shown."""
    from navigator.composition.composer import ClaudeCodeCLIComposer
    from navigator.composition.grounding_validator import ClaudeCodeCLIValidator
    from navigator.composition.writer import ClaudeCodeCLIWriter
    from navigator.corpus.final_corpus import FINAL_CORPUS_VERSION, final_snapshot_fragments, load_final_active
    from navigator.interpretation.interpreter import ClaudeCodeCLIInterpreter
    from navigator.representations.final_meaning import mode_snapshot

    root = Path.cwd()
    final = final_snapshot_fragments(load_final_active())
    layer = None
    if retrieval_layer and mode == "B":  # Retrieval Layer v1: a separate search text for Block 1 cards (mode B only)
        from navigator.representations.retrieval_layer import load_retrieval_layer

        layer = load_retrieval_layer(retrieval_layer, known_ids={f.id for f in final})
    snap = mode_snapshot(final, mode, retrieval_layer=layer)

    def retriever_factory():
        from navigator.providers.embeddings import LocalSentenceTransformerClient
        from navigator.retrieval.diversity import SourceDiversityGuardrail
        from navigator.retrieval.engine import CandidateRetriever

        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        # temporary MVP retrieval diversity guardrail (final corpus only): ≤ 3 cards per source in the candidate pool
        return CandidateRetriever(snap.fragments, LocalSentenceTransformerClient(), cache_root=root / FINAL_EMBEDDINGS,
                                  corpus_version=FINAL_CORPUS_VERSION, card_docs=snap.docs, top_k=pool_size,
                                  diversity_guardrail=SourceDiversityGuardrail(pool_size=pool_size,
                                                                               scan_limit=3 * pool_size))

    return Services(fragments=final, interpreter=ClaudeCodeCLIInterpreter(model=model),
                    composer=ClaudeCodeCLIComposer(model=model), retriever_factory=retriever_factory,
                    writer=ClaudeCodeCLIWriter(model=model, effort="medium"),
                    validator=ClaudeCodeCLIValidator(model=model, effort="medium"), show_quotes=True)


def build_services(model: str = "claude-opus-5-5", corpus: str = "compact", final_mode: str = "A",
                   retrieval_layer: str | None = None, pool_size: int = FINAL_POOL_SIZE) -> Services:
    if corpus == "final":
        return build_final_services(model, final_mode, retrieval_layer, pool_size)
    from navigator.composition.composer import ClaudeCodeCLIComposer
    from navigator.composition.grounding_validator import ClaudeCodeCLIValidator
    from navigator.composition.writer import ClaudeCodeCLIWriter
    from navigator.interpretation.interpreter import ClaudeCodeCLIInterpreter
    from navigator.models.fragment import Fragment

    root = Path.cwd()
    frag_path, manifest_path, cache_root = CORPORA[corpus]
    fragments = [Fragment.model_validate(json.loads(l))
                 for l in (root / frag_path).read_text(encoding="utf-8").splitlines()]

    def retriever_factory():
        from navigator.providers.embeddings import LocalSentenceTransformerClient
        from navigator.retrieval.engine import CandidateRetriever

        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        manifest = json.loads((root / manifest_path).read_text(encoding="utf-8"))
        return CandidateRetriever(fragments, LocalSentenceTransformerClient(), cache_root=root / cache_root,
                                  corpus_version=manifest["corpus_version"])

    from navigator.quotes import load_inventory, quote_for_card

    inventory = load_inventory(root)  # M3.3: 0 READY rows today, so no quote is attached

    return Services(fragments=fragments, interpreter=ClaudeCodeCLIInterpreter(model=model),
                    composer=ClaudeCodeCLIComposer(model=model), retriever_factory=retriever_factory,
                    quote_source=lambda cid: quote_for_card(cid, inventory, root),
                    writer=ClaudeCodeCLIWriter(model=model, effort="medium"),  # M3.3.1: probe showed same quality, ~15% faster
                    validator=ClaudeCodeCLIValidator(model=model, effort="medium"))  # M3.4.2 independent grounding


def serve(port: int = 8770, open_browser: bool = True, trace_dir: Path = Path("reports/prototype-sessions"),
          corpus: str = "compact", final_mode: str = "A", retrieval_layer: str | None = None,
          pool_size: int = FINAL_POOL_SIZE) -> None:
    claude = ensure_claude_on_path()
    services = build_services(corpus=corpus, final_mode=final_mode, retrieval_layer=retrieval_layer, pool_size=pool_size)
    print(f"Корпус: {corpus}" + (f" (тестовый режим, retrieval {final_mode}, цитаты показываются)" if corpus == "final" else "")
          + (f"; retrieval layer: {retrieval_layer}" if corpus == "final" and final_mode == "B" and retrieval_layer else "")
          + (f"; candidate pool: {pool_size}" if corpus == "final" else ""))
    app = App(services, trace_dir)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app))
    url = f"http://127.0.0.1:{port}/"
    print(f"Инструмент Самоанализа: {url}")
    print(f"Developer view: {url}debug")
    if not claude:
        print("ВНИМАНИЕ: команда `claude` не найдена — формулировка вопроса и перспективы работать не будут.")
    threading.Thread(target=services.retriever, daemon=True).start()  # warm up the embedding model
    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    print("Остановить: Ctrl+C")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
