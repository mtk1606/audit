"""Real loopback HTTP/WebSocket recovery; no external exchange connection."""

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import polars as pl
from websockets.asyncio.server import ServerConnection, serve

from asaudit.data.crypto_l3 import FullChannelRecorder, ParquetJournal, collect


def test_forced_disconnect_rebuffers_new_snapshot(tmp_path: Path) -> None:
    state = {"connections": 0}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            assert self.path == "/products/BTC-USD/book?level=3"
            raw = json.dumps(
                {
                    "sequence": state["connections"] * 100,
                    "bids": [["100", "1", "b"]],
                    "asks": [["101", "1", "a"]],
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, format: str, *args: object) -> None:
            pass

    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    recorder = FullChannelRecorder("BTC-USD", ParquetJournal(tmp_path, "BTC-USD"))

    async def exercise() -> None:
        async def handler(ws: ServerConnection) -> None:
            state["connections"] += 1
            n = state["connections"]
            subscription = json.loads(await ws.recv())
            assert subscription["channels"] == ["full"]
            # Sent before REST snapshot arrives, exercising the buffered stream.
            await ws.send(
                json.dumps(
                    {
                        "type": "received",
                        "sequence": n * 100 + 1,
                        "product_id": "BTC-USD",
                        "time": "2026-09-18T00:00:01Z",
                    }
                )
            )
            if n == 1:
                await asyncio.sleep(0.1)
                await ws.close()
            else:
                await ws.wait_closed()

        async with serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            await collect(
                recorder,
                1,
                2,
                0.01,
                10,
                0.05,
                websocket_url=f"ws://127.0.0.1:{port}",
                rest_root=f"http://127.0.0.1:{http.server_port}",
            )

    try:
        asyncio.run(exercise())
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=2)
    assert recorder.messages == 2
    assert recorder.segments == 2
    assert recorder.discontinuities == 1
    rows = pl.read_parquet(list(tmp_path.rglob("*.parquet"))).to_dicts()
    assert sum(r["kind"] == "snapshot" for r in rows) == 2
    assert sum(r["kind"] == "message" for r in rows) == 2
