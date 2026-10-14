#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
轻量化音乐质感转换系统 —— 一键启动脚本
Lightweight Music Timbre Transfer System

用法:
    python main.py            # 默认启动
    python main.py backend    # 仅启动后端
    python main.py frontend   # 仅启动前端
"""

import sys
import os
import subprocess
import time
import webbrowser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")


def get_real_python():
    """
    获取真正的 Python 解释器路径。
    Windows Store 的 python.exe 存根无法正常使用，需要跳过它。
    """
    # 如果当前 Python 可用，直接返回
    python_exe = sys.executable
    if "WindowsApps" not in python_exe:
        return python_exe

    # 被 Windows Store 存根拦截，扫描真实安装位置
    search_paths = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python"),
        r"C:\Program Files\Python",
        r"C:\Program Files (x86)\Python",
    ]
    for base in search_paths:
        if os.path.isdir(base):
            for entry in sorted(os.listdir(base), reverse=True):
                exe_path = os.path.join(base, entry, "python.exe")
                if os.path.isfile(exe_path):
                    return exe_path

    # 回退：尝试系统 PATH 中的 python3
    return "python3" if os.name != "nt" else "python"


def print_banner():
    print()
    print("=" * 58)
    print("  轻量化音乐质感转换系统")
    print("  Lightweight Music Timbre Transfer System")
    print("  作者: 余毅 | 毕业设计作品")
    print("=" * 58)
    print()


def start_backend():
    """启动 Flask 后端"""
    print("[启动] 后端服务 (Flask) 启动中...")
    app_path = os.path.join(BACKEND_DIR, "app.py")
    python_exe = get_real_python()
    return subprocess.Popen(
        [python_exe, app_path],
        cwd=BACKEND_DIR,
        creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0,
    )


def start_frontend():
    """启动 Vite 前端开发服务器"""
    print("[启动] 前端服务 (Vite) 启动中...")

    # 检查 node_modules
    node_modules = os.path.join(FRONTEND_DIR, "node_modules")
    if not os.path.isdir(node_modules):
        print("[前端] 首次运行，安装依赖中...")
        if os.name == "nt":
            subprocess.run(
                ["cmd", "/c", "npm install"], cwd=FRONTEND_DIR, check=True)
        else:
            subprocess.run(
                ["npm", "install"], cwd=FRONTEND_DIR, check=True)
        print("[前端] 依赖安装完成")

    if os.name == "nt":
        return subprocess.Popen(
            ["cmd", "/c", "npm run dev"],
            cwd=FRONTEND_DIR,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
    else:
        return subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=FRONTEND_DIR,
        )


def main():
    print_banner()

    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    processes = []

    try:
        if mode in ("all", "backend"):
            bp = start_backend()
            processes.append(("Backend", bp))
            time.sleep(1.5)

        if mode in ("all", "frontend"):
            fp = start_frontend()
            processes.append(("Frontend", fp))
            time.sleep(1)

        print()
        print("-" * 58)
        print("  系统已启动!")
        print(f"  后端 API:   http://127.0.0.1:5000")
        if mode in ("all", "frontend"):
            print(f"  前端界面:   http://localhost:3000")
        print()
        print("  按 Ctrl+C 停止所有服务")
        print("-" * 58)
        print()

        # 自动打开浏览器
        if mode in ("all", "frontend"):
            time.sleep(2)  # 等 Vite 编译完成
            webbrowser.open("http://localhost:3000")
            print("[系统] 已打开浏览器，等待页面加载...")

        # 等待子进程
        for name, proc in processes:
            proc.wait()

    except KeyboardInterrupt:
        print("\n[系统] 正在停止所有服务...")
        for name, proc in processes:
            proc.terminate()
        print("[系统] 已停止。")


if __name__ == "__main__":
    main()
