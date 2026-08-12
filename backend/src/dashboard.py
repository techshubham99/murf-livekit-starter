"""
Day 7 – Human Help Dashboard Server for ShikshaMitra AI

A lightweight standalone HTTP server that serves the escalation
dashboard and provides API endpoints for managing escalation requests.

Usage:
    cd backend
    uv run python src/dashboard.py

Endpoints:
    GET  /                                  → Dashboard HTML
    GET  /api/escalations                   → All escalation records (JSON)
    POST /api/escalations/<ref_id>/status   → Update escalation status

Runs on port 8765 by default (override with DASHBOARD_PORT env var).
"""

from __future__ import annotations

import json
import logging
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from threading import Thread

from dotenv import load_dotenv

# Ensure backend root is in sys.path when executed directly
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

load_dotenv(backend_root / ".env.local")

from src.database import initialize_database
from src.escalation import (
    get_all_escalations,
    initialize_escalation_table,
    update_escalation_status,
)


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger("dashboard")


# ============================================================
# PATHS
# ============================================================

DASHBOARD_HTML_PATH = Path(__file__).resolve().parent / "dashboard.html"

DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8765"))


# ============================================================
# REQUEST HANDLER
# ============================================================


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the escalation dashboard."""

    def log_message(self, format, *args):
        """Override to use Python logging instead of stderr."""
        logger.info(format, *args)

    def _send_json(self, data: dict | list, status: int = 200) -> None:
        """Send a JSON response with strict no-cache headers."""
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html_bytes: bytes, status: int = 200) -> None:
        """Send an HTML response."""
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html_bytes)))
        self.end_headers()
        self.wfile.write(html_bytes)

    # --------------------------------------------------------
    # GET
    # --------------------------------------------------------

    def do_GET(self) -> None:
        path = self.path.rstrip("/")

        # Dashboard HTML
        if path == "" or path == "/":
            try:
                html = DASHBOARD_HTML_PATH.read_bytes()
                self._send_html(html)
            except FileNotFoundError:
                self._send_html(
                    b"<h1>Dashboard HTML not found</h1>", 500
                )
            return

        # Escalation list API
        if path == "/api/escalations":
            try:
                escalations = get_all_escalations()
                self._send_json({
                    "requests": escalations,
                    "escalations": escalations,
                })
            except Exception as exc:
                logger.exception("Failed to fetch escalations")
                self._send_json(
                    {"error": str(exc)}, 500
                )
            return

        self._send_json({"error": "Not found"}, 404)

    # --------------------------------------------------------
    # POST
    # --------------------------------------------------------

    def do_POST(self) -> None:
        path = self.path.rstrip("/")

        # Update escalation status
        # POST /api/escalations/<reference_id>/status
        if path.startswith("/api/escalations/") and path.endswith("/status"):
            parts = path.split("/")
            # ['', 'api', 'escalations', '<ref_id>', 'status']
            if len(parts) == 5:
                reference_id = parts[3]
                try:
                    content_length = int(
                        self.headers.get("Content-Length", 0)
                    )
                    body = self.rfile.read(content_length)
                    data = json.loads(body) if body else {}
                    new_status = data.get("status", "")

                    result = update_escalation_status(
                        reference_id, new_status
                    )
                    self._send_json(result)
                except Exception as exc:
                    logger.exception("Failed to update status")
                    self._send_json(
                        {"success": False, "error": str(exc)}, 500
                    )
                return

        self._send_json({"error": "Not found"}, 404)

    # --------------------------------------------------------
    # OPTIONS (CORS preflight)
    # --------------------------------------------------------

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


# ============================================================
# SERVER
# ============================================================


def run_dashboard(port: int = DASHBOARD_PORT) -> None:
    """Start the dashboard HTTP server."""

    # Initialize database tables
    initialize_database()
    initialize_escalation_table()

    server = HTTPServer(("0.0.0.0", port), DashboardHandler)

    logger.info("=" * 60)
    logger.info("  ShikshaMitra AI – Human Help Dashboard")
    logger.info("=" * 60)
    logger.info("  URL: http://localhost:%d", port)
    logger.info("  API: http://localhost:%d/api/escalations", port)
    logger.info("=" * 60)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Dashboard server stopped")
        server.server_close()


# ============================================================
# MAIN
# ============================================================


if __name__ == "__main__":
    run_dashboard()
