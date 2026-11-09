#!/usr/bin/env python3
"""feishu_agent_gateway_ws.py — 飞书长连接事件网关 (F4a WS 模式, 园区方案 §5.5)。

模式对比: WS 长连接无需公网回调/nginx (Hector 拍板采用); webhook 版 (feishu_agent_gateway.py + VPS) 并存保留。
机制: lark_oapi ws.Client (app_id+app_secret 握手, SDK 自管心跳/重连) → im.message.receive_v1
      → envelope v1 信封落盘 inbox.jsonl (与 webhook 版同一目录/格式, F4b 消费侧无感)
凭证: FEISHU_APP_ID / FEISHU_APP_SECRET 环境变量 (或 --secret-file)
控制台一次性配置: 开发配置页把事件订阅方式切换为「使用长连接接收事件」+ 添加订阅 im.message.receive_v1 + 发布
用法: .venv-ws/bin/python3 scripts/feishu_agent_gateway_ws.py --secret-file ~/.feishu-gateway.env"""
import argparse
import json
import sys
import threading
import time
import uuid
from pathlib import Path

import lark_oapi as lark
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

STATE = Path("/home/hector/DevSpace/OriginFlow/gateway-state")
INBOX = STATE / "inbox.jsonl"


def to_envelope(data: P2ImMessageReceiveV1) -> dict:
    ev = data.event
    msg = ev.message
    sender = (ev.sender or {}).sender_id
    return {
        "trace_id": f"tr-{uuid.uuid4().hex[:26]}",
        "sender": f"feishu-user:{getattr(sender, 'open_id', 'unknown')}",
        "channel": {"kind": "feishu_thread", "ref": msg.chat_id},
        "task_ref": None,
        "ts": time.time(),
        "message_type": msg.message_type,
        "text": msg.content,
        "message_id": msg.message_id,
        "source": "ws",
    }


def do_event(data: P2ImMessageReceiveV1) -> None:
    env = to_envelope(data)
    with INBOX.open("a", encoding="utf-8") as f:
        f.write(json.dumps(env, ensure_ascii=False) + "\n")
    print(f"[ws-gateway] {env['trace_id'][:14]} from {env['sender'][:30]} text={env['text'][:40]}", flush=True)
    # F4b 扩展点: 此处接信封消费 → 数字员工路由 (herdr prompt / swarm_skill_execute) → bot 回复


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--secret-file", help="env 文件: FEISHU_APP_ID / FEISHU_APP_SECRET")
    a = ap.parse_args()
    app_id = app_secret = None
    if a.secret_file and Path(a.secret_file).exists():
        for ln in Path(a.secret_file).read_text().splitlines():
            if ln.startswith("FEISHU_APP_ID="):
                app_id = ln.split("=", 1)[1].strip()
            elif ln.startswith("FEISHU_APP_SECRET="):
                app_secret = ln.split("=", 1)[1].strip()
    app_id = app_id or "cli_aaac3e0c03a31bdf"
    if not app_secret:
        print("缺 FEISHU_APP_SECRET (--secret-file 或环境变量)", file=sys.stderr)
        sys.exit(2)
    STATE.mkdir(parents=True, exist_ok=True)
    client = lark.ws.Client(app_id, app_secret,
                            event_handler=lark.EventDispatcherHandler.builder("", "").register_p2_im_message_receive_v1(do_event).build(),
                            log_level=lark.LogLevel.INFO)
    print(f"[ws-gateway] long-conn starting app={app_id} inbox={INBOX}", flush=True)
    client.start()


if __name__ == "__main__":
    main()
