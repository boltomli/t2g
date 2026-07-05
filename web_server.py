#!/usr/bin/env python3
"""
Text2Game Web Server
提供 Web 界面用于上传文本、生成 Twine 游戏并在浏览器中运行
"""

import json
import os
import sys
import uuid
import tempfile
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# 项目根目录
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from pi_mode.analyze import TextAnalyzer, LLMClient
from pi_mode.generators.twine import TwineGenerator
from pi_mode.compile_twee import compile_twee

# 全局状态
analyzer = None
progress_info = {"step": "", "progress": 0, "done": False, "error": ""}


def init_analyzer():
    global analyzer
    if analyzer is None:
        client = LLMClient()
        analyzer = TextAnalyzer(client)
    return analyzer


class GameRequestHandler(SimpleHTTPRequestHandler):
    """处理 API 请求和静态文件服务"""

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "":
            self._serve_file(PROJECT_ROOT / "web" / "index.html", "text/html")
        elif path.startswith("/web/"):
            file_path = PROJECT_ROOT / path.lstrip("/")
            self._serve_static(file_path)
        elif path.startswith("/generated/"):
            file_path = PROJECT_ROOT / path.lstrip("/")
            self._serve_static(file_path)
        elif path == "/api/progress":
            self._handle_progress_sse()
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""

        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._json_response(400, {"error": "Invalid JSON"})
            return

        if path == "/api/analyze":
            self._handle_analyze(data)
        elif path == "/api/generate":
            self._handle_generate(data)
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    # ── API Handlers ──

    def _handle_analyze(self, data):
        text = data.get("text", "").strip()
        if not text:
            self._json_response(400, {"error": "文本内容为空"})
            return

        def run():
            global progress_info
            progress_info = {"step": "正在分析文本...", "progress": 0.1, "done": False, "error": ""}
            try:
                ta = init_analyzer()
                progress_info["step"] = "正在调用 LLM 分析..."
                progress_info["progress"] = 0.3
                result = ta.analyze_text(text, use_cache=False)
                progress_info["step"] = "分析完成"
                progress_info["progress"] = 1.0
                progress_info["done"] = True
                progress_info["result"] = result
            except Exception as e:
                progress_info["error"] = str(e)
                progress_info["done"] = True

        threading.Thread(target=run, daemon=True).start()
        self._json_response(200, {"status": "started"})

    def _handle_generate(self, data):
        analysis = data.get("analysis")
        if not analysis:
            self._json_response(400, {"error": "缺少分析数据"})
            return

        def run():
            global progress_info
            progress_info = {"step": "正在生成 Twine 故事...", "progress": 0.1, "done": False, "error": ""}
            try:
                # 保存分析到临时文件
                game_id = f"web_{uuid.uuid4().hex[:8]}"
                tmp_dir = PROJECT_ROOT / "generated_games" / game_id
                tmp_dir.mkdir(parents=True, exist_ok=True)
                analysis_file = tmp_dir / "analysis.json"
                analysis_file.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")

                progress_info["step"] = "正在生成故事内容..."
                progress_info["progress"] = 0.3

                # 生成 Twine 故事
                gen = TwineGenerator(output_dir=str(PROJECT_ROOT / "generated_games"))
                twee_path = gen.generate(str(analysis_file), output_name=game_id, use_llm=True)

                progress_info["step"] = "正在编译 HTML..."
                progress_info["progress"] = 0.7

                # 编译为 HTML
                html_path = compile_twee(Path(twee_path))

                progress_info["step"] = "生成完成"
                progress_info["progress"] = 1.0
                progress_info["done"] = True
                progress_info["url"] = f"/generated/{game_id}/{html_path.name}"
            except Exception as e:
                progress_info["error"] = str(e)
                progress_info["done"] = True

        threading.Thread(target=run, daemon=True).start()
        self._json_response(200, {"status": "started"})

    def _handle_progress_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self._set_cors_headers()
        self.end_headers()

        try:
            while True:
                data = json.dumps(progress_info, ensure_ascii=False)
                self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
                self.wfile.flush()
                if progress_info.get("done"):
                    break
                time.sleep(0.5)
        except (BrokenPipeError, ConnectionResetError):
            pass

    # ── Helpers ──

    def _serve_file(self, file_path, content_type):
        if not file_path.exists():
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(file_path.read_bytes())

    def _serve_static(self, file_path):
        if not file_path.exists():
            self.send_error(404)
            return
        ext = file_path.suffix.lower()
        content_types = {
            ".html": "text/html",
            ".css": "text/css",
            ".js": "application/javascript",
            ".json": "application/json",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".svg": "image/svg+xml",
        }
        ct = content_types.get(ext, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", f"{ct}; charset=utf-8")
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(file_path.read_bytes())

    def _json_response(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _set_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}")


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    server = HTTPServer(("localhost", port), GameRequestHandler)
    print(f"Text2Game Web Server")
    print(f"  http://localhost:{port}")
    print(f"  按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
        server.server_close()


if __name__ == "__main__":
    main()
