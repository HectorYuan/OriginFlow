#!/usr/bin/env python3
"""sync_skills_to_feishu.py — 技能第三分发目标: 飞书云盘文件树 (F3, 园区方案 §5.5)。

分发语义: AS skills/ (SRC canonical, I2 真相) → 云盘 源力觉醒/skills/<name>/SKILL.md
         + _MANIFEST.yaml (name/source_commit/synced_at) — 目录即注册表, 云盘是分发镜像非真相。
登录: lark-cli user 身份 (lark-shared 单源)。红线: 只写源力觉醒目录树, 人类盘区只读。
用法: python3 scripts/sync_skills_to_feishu.py [skill-name ...]   # 缺省同步全部 hq-* 技能"""
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

AS_SKILLS = Path("/home/hector/DevSpace/AgentSwarm/skills")
CAMPUS_FOLDER = "PyUKf5r4sldfS1dg9lVceGHjnAh"  # 云盘「源力觉醒」(重复文件夹待人工确认, 见方案 §5.5 F3)
SKILLS_DIR_NAME = "skills"


def lark(*args: str) -> dict:
    r = subprocess.run(["lark-cli", "drive", *args, "--as", "user", "--format", "json"],
                       capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": r.stdout + r.stderr}


def ensure_folder(parent: str, name: str) -> str:
    """子文件夹幂等创建: 先列后建 (同名复用)。"""
    d = lark("files", "list", "--folder-token", parent)
    for f in (d.get("data", {}).get("files") or []):
        if f.get("name") == name and f.get("type") == "folder":
            return f["token"]
    c = lark("+create-folder", "--folder-token", parent, "--name", name)
    return c["data"]["folder_token"]


def upload(parent: str, local: Path, name: str) -> str:
    # lark-cli +upload 路径白名单: 仅 cwd / /tmp (注意 mkstemp 默认 /var/tmp 会被拒!) → 显式 dir=/tmp
    import shutil, tempfile
    tmp = Path(tempfile.mkstemp(suffix=local.suffix, dir="/tmp")[1])
    shutil.copy(local, tmp)
    u = lark("+upload", "--folder-token", parent, "--file", str(tmp), "--name", name)
    tmp.unlink(missing_ok=True)
    if isinstance(u.get("error"), dict):
        return f"ERR:{u['error'].get('message', '?')[:60]}"
    return u.get("data", {}).get("file_token") or "ERR:no_token"

def main() -> None:
    names = sys.argv[1:] or sorted(p.parent.name for p in AS_SKILLS.glob("hq-*/SKILL.md"))
    skills_root = ensure_folder(CAMPUS_FOLDER, SKILLS_DIR_NAME)
    manifest = []
    for name in names:
        src = AS_SKILLS / name / "SKILL.md"
        if not src.exists():
            print(f"skip {name} (SKILL.md 缺失)")
            continue
        # 扁平化: skills/<name>-SKILL.md (每技能一文件; 子文件夹模式在部分 folder token 上报 1061044, 扁平更稳)
        token = upload(skills_root, src, f"{name}-SKILL.md")
        commit = subprocess.run(["git", "-C", str(AS_SKILLS.parent), "log", "-1", "--format=%h",
                                 "--", f"skills/{name}"], capture_output=True, text=True).stdout.strip() or "uncommitted"
        manifest.append({"name": name, "source_commit": commit, "file_token": token})
        print(f"sync {name} -> skills/{name}-SKILL.md ({token}) src:{commit}")
    if manifest:
        mf = f"# 技能分发清单 (gen: sync_skills_to_feishu.py)\nsynced_at: \"{date.today()}\"\nskills:\n" + \
             "\n".join(f"  - {{name: {m['name']}, source_commit: {m['source_commit']}, file_token: {m['file_token']}}}" for m in manifest)
        upload(skills_root, Path(_tmp_manifest(mf)), "_MANIFEST.yaml")
        print(f"manifest: {len(manifest)} skills")


def _tmp_manifest(content: str) -> str:
    import tempfile
    fd, p = tempfile.mkstemp(suffix=".yaml")
    Path(p).write_text(content, encoding="utf-8")
    return p


if __name__ == "__main__":
    main()
