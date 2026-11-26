import json
import sqlite3
from pathlib import Path
from typing import Any


class Store:
    def __init__(self, path: str | Path):
        self.connection = sqlite3.connect(str(path), check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.executescript("""
        CREATE TABLE IF NOT EXISTS signals (id INTEGER PRIMARY KEY, symbol TEXT NOT NULL, action TEXT NOT NULL, timestamp TEXT NOT NULL, payload TEXT NOT NULL, UNIQUE(symbol,timestamp));
        CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, client_order_id TEXT UNIQUE NOT NULL, symbol TEXT NOT NULL, side TEXT NOT NULL, quantity INTEGER NOT NULL, status TEXT NOT NULL, broker_order_id TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, event TEXT NOT NULL, details TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        self.connection.commit()

    def audit(self, event: str, details: dict[str, Any]) -> None:
        self.connection.execute("INSERT INTO audit(event,details) VALUES (?,?)", (event, json.dumps(details, default=str)))
        self.connection.commit()

    def record_signal(self, signal: dict[str, Any]) -> None:
        self.connection.execute("INSERT OR IGNORE INTO signals(symbol,action,timestamp,payload) VALUES(?,?,?,?)", (signal["symbol"],signal["action"],signal["timestamp"],json.dumps(signal)))
        self.connection.commit()

    def record_order(self, client_order_id: str, symbol: str, side: str, quantity: int,
                     status: str, broker_order_id: str | None = None, payload: dict[str, Any] | None = None) -> None:
        self.connection.execute("INSERT INTO orders(client_order_id,symbol,side,quantity,status,broker_order_id,payload) VALUES(?,?,?,?,?,?,?) ON CONFLICT(client_order_id) DO UPDATE SET status=excluded.status, broker_order_id=COALESCE(excluded.broker_order_id,orders.broker_order_id), payload=excluded.payload", (client_order_id,symbol,side,quantity,status,broker_order_id,json.dumps(payload or {})))
        self.connection.commit()

    def has_order(self, client_order_id: str) -> bool:
        return self.connection.execute("SELECT 1 FROM orders WHERE client_order_id=?", (client_order_id,)).fetchone() is not None

    def rows(self, table: str, limit: int = 100) -> list[dict[str, Any]]:
        if table not in {"signals", "orders", "audit"}: raise ValueError("Unsupported table")
        return [dict(row) for row in self.connection.execute(f"SELECT * FROM {table} ORDER BY id DESC LIMIT ?", (limit,))]

    def close(self) -> None:
        self.connection.close()
