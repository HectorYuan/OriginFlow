#!/usr/bin/env python3
"""feishu_agent_gateway.py — 飞书事件订阅接收端点 (F4a 预备件, 园区方案 §5.5 F4)。

职责 (v0 骨架, 回调配置就绪后即启用):
  1. url_verification 挑战应答 (飞书开放平台配置回调时的握手)
  2. im.message.receive_v1 事件接收 → envelope v1 信封落盘 (JSONL, 本机 agent 消费)
  3. 可选 ACK 回复 (需 FEISHU_BOT_TOKEN 环境变量; 无则只落盘)
约定:
  - 只处理 p2p/群内 @bot 文本消息; 指令白名单在 MSG_HANDLERS (F4b 扩展点)
  - 事件落盘 STATE_DIR/inbox.jsonl, 每行一个 envelope (trace_id/sender/channel/task_ref)
  - 纪律: 只读接收, 不直写 registry; 响应走 bot 发消息通道
部署 (VPS): 见 deploy/feishu-agent-gateway.service; 开放平台回调 URL = https://<vps>/webhook/feishu
用法: python3 feishu_agent_gateway.py [--port 9806] [--state-dir ./gateway-state]"""
import argparse
import json
import os
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

STATE_DIR = Path("./gateway-state")
INBOX = None


def envelope(msg_event: dict) -> dict:
    """飞书消息事件 → TRINITY-COMM envelope v1 形态落盘。"""
    msg = (msg_event.get("event") or {}).get("message") or {}
    sender_id = (((msg_event.get("event") or {}).get("sender") or {}).get("sender_id") or {}).get("open_id", "unknown")
    return {
        "trace_id": f"tr-{uuid.uuid4().hex[:26]}",
        "sender": f"feishu-user:{sender_id}",
        "channel": {"kind": "feishu_thread", "ref": msg.get("chat_id", "")},
        "task_ref": None,
        "ts": time.time(),
        "message_type": msg.get("message_type", ""),
        "text": msg.get("content", ""),
        "message_id": msg.get("message_id", ""),
        "raw_event": msg_event,
    }


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/webhook/feishu":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            body = {}
        # 1) url_verification 握手
        if body.get("type") == "url_verification":
            self._respond(200, {"challenge": body.get("challenge", "")})
            print(f"[gateway] url_verified ts={body.get('timestamp')}")
            return
        # 2) 事件分发 (v2 schema: header.event_type; v1: event_type)
        etype = ((body.get("header") or {}).get("event_type")) or body.get("event_type") or ""
        if etype == "im.message.receive_v1":
            env = envelope(body)
            with INBOX.open("a", encoding="utf-8") as f:
                f.write(json.dumps(env, ensure_ascii=False) + "\n")
            print(f"[gateway] msg {env['trace_id']} from {env['sender'][:30]} text={env['text'][:40]}")
            self._respond(200, {"ok": True})
            self._ack(env)  # 可选 bot ACK (无 token 时静默)
            return
        self._respond(200, {"ok": True, "ignored": etype})

    def _respond(self, code: int, obj: dict):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _ack(self, env: dict):
        """F4b 扩展点: 路由到数字员工 (herdr prompt / swarm_skill_execute); v0 仅 bot ACK。"""
        token = os.environ.get("FEISHU_BOT_TOKEN", "")
        if not token or not env.get("message_id"):
            return
        import urllib.request
        req = urllib.request.Request(
            "https://open.feishu.cn/open-apis/im/v1/messages",
            data=json.dumps({"receive_id_type": "chat_id", "content": json.dumps({"text": f"已收到 (trace={env['trace_id'][:12]}), 数字员工处理中"}), "msg_type": "text", "receive_id": env["channel"]["ref"]}).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req, timeout=5)
        except OSError:
            pass


def main() -> None:
    global INBOX
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9806)
    ap.add_argument("--state-dir", default="./gateway-state")
    a = ap.parse_args()
    STATE_DIR = Path(a.state_dir)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    INBOX = STATE_DIR / "inbox.jsonl"
    print(f"[gateway] listening :{a.port} -> {INBOX}")
    HTTPServer(("0.0.0.0", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
