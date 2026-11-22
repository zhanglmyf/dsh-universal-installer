#!/usr/bin/env python3
"""
本地自检（纯标准库、无网络）：验证项目完整、配置模板合法、无隐私泄漏。

用法：python3 scripts/healthcheck.py
"""
from __future__ import annotations

import ast
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED = [
    "README.md", "README.en.md", "LICENSE", "config.example.json",
    "deploy.py", "assets/banner.svg",
    "docs/DEPLOY-MODES.md", "docs/PLATFORMS.md",
    "docs/CONFIGURATION.md", "docs/TROUBLESHOOTING.md",
]
# 通用敏感模式检测（不写入任何真实姓名/主机/路径字面量，避免自指与观感问题）
PRIVATE = [
    (re.compile(r"(?<!<)\b(?:192\.168|10)\.\d+\.\d+"), "内网 IP"),
    (re.compile(r"(?<!<)\b172\.(1[6-9]|2\d|3[01])\.\d+\.\d+"), "容器网段 IP"),
    (re.compile(r"\bghp_[A-Za-z0-9]{20,}"), "GitHub token"),
    (re.compile(r"\b(?:nvapi|sk)-[A-Za-z0-9]{20,}"), "API key"),
    (re.compile(r"/home/[a-z][a-z0-9_-]{2,}/\.npm/_npx"), "宿主 npx 缓存路径"),
]

ok = True
def report(flag, msg):
    global ok
    print(("  OK   " if flag else "  FAIL ") + msg)
    if not flag:
        ok = False

print("=== 1. 必需文件 ===")
for rel in REQUIRED:
    report((ROOT / rel).exists(), rel)

print("\n=== 2. Python 语法 ===")
for py in ROOT.rglob("*.py"):
    if ".git" in py.parts:
        continue
    try:
        ast.parse(py.read_text(encoding="utf-8"))
        report(True, str(py.relative_to(ROOT)))
    except SyntaxError as e:
        report(False, f"{py.relative_to(ROOT)}: {e}")

print("\n=== 3. 配置模板 ===")
try:
    cfg = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
    report(all(k in cfg for k in ("deploy", "target", "dsh", "node", "ollama", "service")),
           "config.example.json 关键段齐全")
except Exception as e:
    report(False, f"配置解析失败: {e}")

print("\n=== 4. SVG 合法性 ===")
try:
    ET.parse(ROOT / "assets" / "banner.svg")
    report(True, "banner.svg 是合法 XML")
except Exception as e:
    report(False, f"banner.svg: {e}")

print("\n=== 5. 脱敏扫描 ===")
scan = [f for f in ROOT.rglob("*") if f.is_file() and ".git" not in f.parts
        and f != Path(__file__).resolve() and f.suffix in (".py", ".md", ".json", ".yml", ".svg")]
leaks = []
for f in scan:
    text = f.read_text(encoding="utf-8", errors="ignore")
    for pat, label in PRIVATE:
        for m in pat.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            leaks.append((str(f.relative_to(ROOT)), line, label, m.group()[:30]))
if leaks:
    for f, line, label, val in leaks:
        report(False, f"{f}:{line} {label}: {val}")
else:
    report(True, "未发现私人信息")

print("\n" + "=" * 40)
print("自检通过 ✓" if ok else "自检未通过，请修复 FAIL 项")
sys.exit(0 if ok else 1)
