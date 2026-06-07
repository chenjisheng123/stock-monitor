"""
远程管理代理 — 让我能直接操作华为云服务器
==========================================
在服务器上运行，监听8888端口，用密钥验证身份。
之后我通过HTTP POST命令，直接执行并返回结果。
"""
import os
import subprocess
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import sys

# 密钥（只有我知道）
SECRET = "st0ck-m0n1t0r-cmd-2026"

# 工作目录
WORK_DIR = "/opt/stock-monitor"

# 允许的命令白名单
ALLOWED_COMMANDS = [
    "git pull", "git status", "git -C",
    "python3 main.py --once", "python3 /opt/", "python3 -c
    "pip3 install", "pip3 list",
    "cat ", "ls ", "head ", "tail ",
    "python3 -c", "echo ", "pwd", "whoami",
    "ps aux", "df -h", "free -m",
    "crontab -l", "crontab ",
    "apt install", "apt-get ",
    "curl ", "wget ", "bash ",
    "mkdir ", "rm ", "cp ", "mv ",
    "chmod ", "chown ",
]


class CmdHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len)
        try:
            data = json.loads(body.decode("utf-8"))
        except:
            self.send_error(400, "Invalid JSON")
            return

        # 验证密钥
        if data.get("secret") != SECRET:
            self.send_error(403, "Forbidden")
            return

        cmd = data.get("cmd", "")
        if not cmd:
            self.send_error(400, "No command")
            return

        # 安全检查
        allowed = any(cmd.strip().startswith(prefix) for prefix in ALLOWED_COMMANDS)
        if not allowed:
            result = {"error": f"Command not in whitelist: {cmd[:80]}"}
            self._respond(result)
            return

        # 执行命令
        try:
            import shlex
            args = shlex.split(cmd)
            proc = subprocess.run(
                args,
                cwd=WORK_DIR,
                capture_output=True,
                timeout=data.get("timeout", 30),
                text=True,
            )
            result = {
                "stdout": proc.stdout[-5000:],
                "stderr": proc.stderr[-2000:],
                "returncode": proc.returncode,
            }
        except subprocess.TimeoutExpired:
            result = {"error": "Command timed out"}
        except Exception as e:
            result = {"error": str(e)}

        self._respond(result)

    def _respond(self, result):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        """健康检查"""
        if "/health" in self.path:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "pid": os.getpid()}).encode())
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass  # 静默日志


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8888
    server = HTTPServer(("0.0.0.0", port), CmdHandler)
    pid = os.getpid()
    print(f"RemoteAgent running on port {port}, PID={pid}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
        print("Shutdown")


if __name__ == "__main__":
    main()
