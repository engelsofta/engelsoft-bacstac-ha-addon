"""Safe, versioned SQLite inventory cache for BACnet discovery.

Created by engelsofta in 2026 for the modified Engelsoft BACstac distribution.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from typing import Any

from const import LOGGER

_SCHEMA_VERSION = 1
_MAX_CACHE_AGE_SECONDS = 30 * 24 * 60 * 60
_MAX_PAYLOAD_BYTES = 20 * 1024 * 1024
_MISSING_OBJECT_TOLERANCE = 2
_DECREASE_CONFIRMATIONS = 3


class InventoryCache:
    """Persist only confirmed, complete per-device inventory snapshots."""

    def __init__(self, path: str = "/data/engelsoft_inventory_cache.sqlite3") -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(self.path, timeout=10)
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            self._initialize(connection)
            return connection
        except sqlite3.DatabaseError as err:
            if connection is not None:
                connection.close()
            corrupt_suffix = f".corrupt-{int(time.time())}"
            for suffix in ("", "-wal", "-shm"):
                try:
                    os.replace(
                        f"{self.path}{suffix}",
                        f"{self.path}{corrupt_suffix}{suffix}",
                    )
                except OSError:
                    pass
            LOGGER.warning("Ignoring corrupt BACnet inventory cache: %s", err)
            connection = sqlite3.connect(self.path, timeout=10)
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            self._initialize(connection)
            return connection

    @staticmethod
    def _initialize(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory (
                device_id TEXT PRIMARY KEY,
                schema_version INTEGER NOT NULL,
                updated_at REAL NOT NULL,
                object_count INTEGER NOT NULL,
                checksum TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_decrease (
                device_id TEXT PRIMARY KEY,
                fingerprint TEXT NOT NULL,
                confirmations INTEGER NOT NULL
            )
            """
        )
        connection.commit()

    @staticmethod
    def _encode(payload: dict[str, Any]) -> tuple[str, str]:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        if len(encoded.encode("utf-8")) > _MAX_PAYLOAD_BYTES:
            raise ValueError("inventory cache payload exceeds safety limit")
        checksum = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        return encoded, checksum

    def load_all(self) -> tuple[dict[str, Any], dict[str, Any]]:
        """Load all valid, recent device snapshots and return diagnostics."""
        restored: dict[str, Any] = {}
        diagnostics = {"devices": 0, "objects": 0, "ignored": 0}
        now = time.time()

        try:
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT device_id, schema_version, updated_at, object_count, checksum, payload FROM inventory"
                ).fetchall()
        except (OSError, sqlite3.DatabaseError) as err:
            LOGGER.warning("Unable to read BACnet inventory cache: %s", err)
            diagnostics["ignored"] += 1
            return restored, diagnostics

        for device_id, schema_version, updated_at, object_count, checksum, encoded in rows:
            try:
                if int(schema_version) != _SCHEMA_VERSION:
                    raise ValueError("unsupported cache schema")
                if now - float(updated_at) > _MAX_CACHE_AGE_SECONDS:
                    raise ValueError("cache is older than 30 days")
                if hashlib.sha256(encoded.encode("utf-8")).hexdigest() != checksum:
                    raise ValueError("checksum mismatch")
                payload = json.loads(encoded)
                if not isinstance(payload, dict) or device_id not in payload:
                    raise ValueError("invalid device payload")
                device_payload = payload[device_id]
                if not isinstance(device_payload, dict) or device_id not in device_payload:
                    raise ValueError("missing BACnet device object")
                actual_count = sum(1 for key in device_payload if key != device_id)
                if actual_count != int(object_count):
                    raise ValueError("object count mismatch")
            except (TypeError, ValueError, json.JSONDecodeError) as err:
                diagnostics["ignored"] += 1
                LOGGER.warning("Ignoring invalid inventory cache for %s: %s", device_id, err)
                continue

            restored.update(payload)
            diagnostics["devices"] += 1
            diagnostics["objects"] += int(object_count)

        return restored, diagnostics

    def store_device(
        self,
        device_id: str,
        payload: dict[str, Any],
        object_count: int,
    ) -> dict[str, Any]:
        """Atomically store a complete device inventory with decrease protection."""
        encoded, checksum = self._encode(payload)
        device_payload = payload.get(device_id, {})
        structure = "\n".join(
            sorted(key for key in device_payload if key != device_id)
        )
        structure_fingerprint = hashlib.sha256(
            structure.encode("utf-8")
        ).hexdigest()
        result = {
            "saved": False,
            "deferred": False,
            "confirmations": 0,
            "objects": int(object_count),
        }

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT object_count FROM inventory WHERE device_id = ?",
                (device_id,),
            ).fetchone()

            previous_count = int(current[0]) if current else None
            large_decrease = (
                previous_count is not None
                and int(object_count) < previous_count - _MISSING_OBJECT_TOLERANCE
            )

            if large_decrease:
                pending = connection.execute(
                    "SELECT fingerprint, confirmations FROM pending_decrease WHERE device_id = ?",
                    (device_id,),
                ).fetchone()
                confirmations = (
                    int(pending[1]) + 1
                    if pending and pending[0] == structure_fingerprint
                    else 1
                )
                connection.execute(
                    """
                    INSERT INTO pending_decrease(device_id, fingerprint, confirmations)
                    VALUES (?, ?, ?)
                    ON CONFLICT(device_id) DO UPDATE SET
                        fingerprint = excluded.fingerprint,
                        confirmations = excluded.confirmations
                    """,
                    (device_id, structure_fingerprint, confirmations),
                )
                result.update({"deferred": confirmations < _DECREASE_CONFIRMATIONS, "confirmations": confirmations})
                if confirmations < _DECREASE_CONFIRMATIONS:
                    connection.commit()
                    return result

            connection.execute(
                """
                INSERT INTO inventory(device_id, schema_version, updated_at, object_count, checksum, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    schema_version = excluded.schema_version,
                    updated_at = excluded.updated_at,
                    object_count = excluded.object_count,
                    checksum = excluded.checksum,
                    payload = excluded.payload
                """,
                (
                    device_id,
                    _SCHEMA_VERSION,
                    time.time(),
                    int(object_count),
                    checksum,
                    encoded,
                ),
            )
            connection.execute(
                "DELETE FROM pending_decrease WHERE device_id = ?",
                (device_id,),
            )
            connection.commit()

        result["saved"] = True
        return result
