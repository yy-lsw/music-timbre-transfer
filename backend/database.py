#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SQLite storage for uploads and conversion history."""

import sqlite3

from .config import DB_PATH


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversion_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_filename TEXT NOT NULL,
                output_filename TEXT NOT NULL,
                style TEXT NOT NULL,
                style_label TEXT NOT NULL,
                file_size_mb REAL,
                duration_sec REAL,
                conversion_time_sec REAL,
                rtf REAL,
                status TEXT DEFAULT 'completed',
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
            """
        )
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(conversion_history)")
        }
        if "rtf" not in columns:
            conn.execute(
                "ALTER TABLE conversion_history ADD COLUMN rtf REAL"
            )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS upload_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT UNIQUE NOT NULL,
                original_filename TEXT NOT NULL,
                file_size_mb REAL,
                duration_sec REAL,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
            """
        )


def save_upload(file_id, original_filename, file_size_mb, duration_sec):
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO upload_files
                (file_id, original_filename, file_size_mb, duration_sec)
            VALUES (?, ?, ?, ?)
            """,
            (file_id, original_filename, file_size_mb, duration_sec),
        )


def get_upload(file_id):
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM upload_files WHERE file_id = ?", (file_id,)
        ).fetchone()
        return dict(row) if row else None


def add_history(
    original_filename,
    output_filename,
    style,
    style_label,
    file_size_mb,
    duration_sec,
    conversion_time_sec,
    rtf,
):
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO conversion_history
                (original_filename, output_filename, style, style_label,
                 file_size_mb, duration_sec, conversion_time_sec, rtf)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                original_filename,
                output_filename,
                style,
                style_label,
                round(file_size_mb, 2),
                round(duration_sec, 2),
                round(conversion_time_sec, 3),
                round(rtf, 4),
            ),
        )


def get_history(limit=20):
    limit = max(1, min(int(limit), 100))
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM conversion_history
            ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
