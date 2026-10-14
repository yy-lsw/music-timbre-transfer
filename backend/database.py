#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite 数据库模块 —— 对应论文 4.3节：数据存储模块

管理用户配置与转换历史记录。
"""

import sqlite3
import os
import time
from config import DB_PATH


def get_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库表（对应论文 表4.3：数据库表设计）"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS conversion_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_filename TEXT NOT NULL,
            output_filename TEXT NOT NULL,
            style TEXT NOT NULL,
            style_label TEXT NOT NULL,
            file_size_mb REAL,
            duration_sec REAL,
            conversion_time_sec REAL,
            avg_frame_latency_ms REAL,
            status TEXT DEFAULT 'completed',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    # 默认配置
    c.execute("""
        INSERT OR IGNORE INTO user_config (key, value)
        VALUES ('default_save_path', 'outputs/')
    """)
    c.execute("""
        INSERT OR IGNORE INTO user_config (key, value)
        VALUES ('default_format', 'wav')
    """)
    conn.commit()
    conn.close()


def add_history(original_filename, output_filename, style, style_label,
                file_size_mb, duration_sec, conversion_time_sec, avg_latency_ms):
    """插入一条转换记录"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO conversion_history
            (original_filename, output_filename, style, style_label,
             file_size_mb, duration_sec, conversion_time_sec, avg_frame_latency_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (original_filename, output_filename, style, style_label,
          round(file_size_mb, 2), round(duration_sec, 1),
          round(conversion_time_sec, 1), round(avg_latency_ms, 1)))
    conn.commit()
    conn.close()


def get_history(limit=20):
    """获取最近 N 条转换记录"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM conversion_history
        ORDER BY created_at DESC LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_config(key):
    """获取用户配置"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT value FROM user_config WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row["value"] if row else None


def set_config(key, value):
    """保存用户配置"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO user_config (key, value) VALUES (?, ?)
    """, (key, value))
    conn.commit()
    conn.close()
