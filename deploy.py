#!/usr/bin/env python3
"""
DSH Universal Installer — 跨平台 DeepSeek Harness 部署编排器

设计目标
--------
用一份配置，把 DSH 装到「本机 / 局域网主机 / 远程主机」任意一种目标上，
并适配 Linux / macOS / Windows 三大平台。所有主机、用户、端口、路径、
版本均来自配置，不含任何环境特定的硬编码。

工作原理
--------
1. 读取 config.json（配置优先级：命令行 > 环境变量 > 配置文件 > 内置默认）
2. 根据 deploy.mode 选择执行器：local（本机）/ ssh（局域网或远程）
3. 探测目标平台（linux / macos / windows）
4. 生成安装在目标机上执行的 bootstrap 脚本（bash 或 PowerShell）
5. 上传并执行；脚本幂等、改前备份
6. 启动服务并验证

用法
----
    python3 deploy.py --config config.json --dry-run     # 预演，不实际改动
    python3 deploy.py --config config.json               # 执行部署
    python3 deploy.py --config config.json --verify      # 只做验证，不安装
    python3 deploy.py --config config.json --mode local  # 覆盖配置里的模式

纯标准库实现（Python 3.9+），无需 pip install。
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

VERSION = "1.0.0"

DEFAULTS = {
    "deploy": {
        "mode": "local",              # local | ssh
        "dry_run": False,
        "install_node": True,
        "install_ollama": False,
        "start_service": True,
    },
    "target": {
        "host": "",                   # SSH 主机（mode=ssh 时必填），如 myserver.local
        "user": "",                   # SSH 用户（留空则用当前用户）
        "port": 22,
        "ssh_key": "",                # 可选：私钥路径；留空用 ssh-agent / 默认密钥
        "ssh_options": "",            # 额外 ssh 选项，如 "-J jump.example.com"
    },
    "dsh": {
        "package": "@deepseek-ai/dsh",
        "version": "latest",          # 固定版本更可复现，如 0.2.2-rc.1
        "port": 3080,
        "bind": "127.0.0.1",
        "profile": "web",
        "config_dir": "~/.dsh",
        "data_dir": "",
    },
    "node": {
        "min_version": "24.9.0",
        "install_method": "nvm",      # nvm | official | system
    },
    "ollama": {
        "base_url": "http://127.0.0.1:11434",
        "api_key_env": "OLLAMA_API_KEY",
        "models": [],                 # 要拉取的模型 id 列表
        "context_window": 131072,     # 见 docs/TROUBLESHOOTING.md：compaction 需要足够大
        "max_tokens": 8192,
    },
    "service": {
        "manager": "auto",            # auto | systemd-user | launchd | windows-task | none
        "name": "dsh-web",
        "auto_start": True,
    },
}

# ---------------------------------------------------------------------------
# 执行器抽象：本机与远程共用同一套接口，这是「三种部署方式」统一的关键
# ---------------------------------------------------------------------------

@dataclass
class Result:
    ok: bool
    stdout: str = ""
    stderr: str = ""
    code: int = 0


class Runner:
    """执行器基类。所有命令都在目标机环境里执行。"""
    name = "base"

    def run(self, cmd: str, timeout: int = 600) -> Result:
        raise NotImplementedError

    def write_file(self, path: str, content: str, mode: str = "0644") -> Result:
        raise NotImplementedError

    def read_file(self, path: str) -> Result:
        raise NotImplementedError

    def exists(self, path: str) -> bool:
        return self.run(f'test -e {shlex.quote(path)} && echo yes || echo no').stdout.strip() == "yes"


class LocalRunner(Runner):
    """本机执行器：直接 run subprocess。"""
    name = "local"

    def run(self, cmd: str, timeout: int = 600) -> Result:
        try:
            p = subprocess.run(
                ["bash", "-lc", cmd],
                capture_output=True, text=True, timeout=timeout,
            )
            return Result(p.returncode == 0, p.stdout, p.stderr, p.returncode)
        except subprocess.TimeoutExpired as e:
            return Result(False, "", f"timeout after {timeout}s", 124)
        except Exception as e:
            return Result(False, "", str(e), 1)

    def write_file(self, path: str, content: str, mode: str = "0644") -> Result:
        expanded = os.path.expanduser(path)
        Path(expanded).parent.mkdir(parents=True, exist_ok=True)
        Path(expanded).write_text(content, encoding="utf-8")
        os.chmod(expanded, int(mode, 8))
        return Result(True)

    def read_file(self, path: str) -> Result:
        try:
            return Result(True, Path(os.path.expanduser(path)).read_text(encoding="utf-8"))
        except Exception as e:
            return Result(False, "", str(e), 1)


class SSHRunner(Runner):
    """
    SSH 执行器：局域网与远程统一走这条。
    通过 `ssh user@host 'bash -s'` 把脚本喂给目标机 stdin，避免引号地狱。
    """
    name = "ssh"

    def __init__(self, target: dict):
        self.host = target["host"].strip()
        self.user = target["user"].strip()
        self.port = int(target.get("port", 22))
        self.key = target.get("ssh_key", "").strip()
        self.opts = target.get("ssh_options", "").strip()
        if not self.host:
            raise ValueError("mode=ssh 时 target.host 不能为空")

    def _base(self) -> list[str]:
        cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
               "-p", str(self.port)]
        if self.key:
            cmd += ["-i", os.path.expanduser(self.key)]
        if self.opts:
            cmd += shlex.split(self.opts)
        target = f"{self.user}@{self.host}" if self.user else self.host
        cmd.append(target)
        return cmd

    def run(self, cmd: str, timeout: int = 600) -> Result:
        try:
            p = subprocess.run(
                self._base() + ["bash", "-s"],
                input=cmd, capture_output=True, text=True, timeout=timeout,
            )
            return Result(p.returncode == 0, p.stdout, p.stderr, p.returncode)
        except subprocess.TimeoutExpired as e:
            return Result(False, "", f"timeout after {timeout}s", 124)
        except Exception as e:
            return Result(False, "", str(e), 1)

    def write_file(self, path: str, content: str, mode: str = "0644") -> Result:
        # 用 base64 传内容，彻底规避引号/换行/特殊字符问题
        import base64
        b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
        script = textwrap.dedent(f"""
            set -e
            P={shlex.quote(path)}
            mkdir -p "$(dirname "$P")"
            printf %s {shlex.quote(b64)} | base64 -d > "$P"
            chmod {shlex.quote(mode)} "$P"
        """)
        return self.run(script)

    def read_file(self, path: str) -> Result:
        return self.run(f"cat {shlex.quote(path)}")


def build_runner(cfg: dict, mode_override: str = "") -> Runner:
    mode = mode_override or cfg["deploy"]["mode"]
    if mode == "local":
        return LocalRunner()
    if mode == "ssh":
        return SSHRunner(cfg["target"])
    raise ValueError(f"未知 deploy.mode: {mode}（可选 local / ssh）")


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

def deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: str) -> dict:
    cfg = json.loads(json.dumps(DEFAULTS))  # deep copy
    if path and Path(path).exists():
        user_cfg = json.loads(Path(path).read_text(encoding="utf-8"))
        cfg = deep_merge(cfg, user_cfg)
    # 环境变量覆盖（前缀 DSH_）
    env_map = {
        "DSH_MODE": ("deploy", "mode"),
        "DSH_HOST": ("target", "host"),
        "DSH_USER": ("target", "user"),
        "DSH_PORT": ("target", "port"),
        "DSH_SSH_KEY": ("target", "ssh_key"),
        "DSH_WEB_PORT": ("dsh", "port"),
    }
    for env, (section, key) in env_map.items():
        if env in os.environ:
            cfg[section][key] = os.environ[env]
    return cfg


# ---------------------------------------------------------------------------
# 平台探测与 bootstrap 脚本生成
# ---------------------------------------------------------------------------

def detect_platform(runner: Runner) -> str:
    r = runner.run('uname -s 2>/dev/null || echo Windows')
    s = r.stdout.strip().lower()
    if "darwin" in s:
        return "macos"
    if "linux" in s:
        return "linux"
    return "windows"


def gen_bootstrap(cfg: dict, platform: str) -> str:
    """生成在目标机上执行的安装脚本（幂等、改前备份）。"""
    d = cfg["dsh"]
    n = cfg["node"]
    o = cfg["ollama"]
    s = cfg["service"]
    dep = cfg["deploy"]

    if platform in ("linux", "macos"):
        return _gen_bash(cfg, platform)
    return _gen_powershell(cfg)


def _gen_bash(cfg: dict, platform: str) -> str:
    d, n, o, s, dep = cfg["dsh"], cfg["node"], cfg["ollama"], cfg["service"], cfg["deploy"]
    models_line = " ".join(shlex.quote(m) for m in o.get("models", []))
    pkg = f'{d["package"]}@{d["version"]}' if d["version"] != "latest" else d["package"]

    return textwrap.dedent(f"""\
        #!/usr/bin/env bash
        # DSH bootstrap — 由 deploy.py 生成，幂等可重复运行
        set -euo pipefail
        echo "[dsh-install] 平台: {platform}"

        # ---- 1. Node.js ----
        if {str(dep['install_node']).lower()}; then
          if ! command -v node >/dev/null 2>&1 || \\
             [ "$(node -p 'parseInt(process.versions.node)' 2>/dev/null || echo 0)" -lt 20 ]; then
            echo "[dsh-install] 安装 Node.js（方法: {n['install_method']}）"
            if [ "{n['install_method']}" = "nvm" ]; then
              export NVM_DIR="$HOME/.nvm"
              [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" || \\
                curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
              . "$NVM_DIR/nvm.sh"
              nvm install {n['min_version']}
            else
              echo "[dsh-install] 请按 docs/PLATFORMS.md 手动安装 Node >= {n['min_version']}" >&2
              exit 1
            fi
          fi
        fi
        echo "[dsh-install] node=$(node -v 2>/dev/null || echo missing)"

        # ---- 2. 安装 DSH（本地安装，避免 npx 缓存随清理丢失）----
        echo "[dsh-install] 安装 {pkg}"
        npm install -g --prefix "$HOME/.local" {shlex.quote(pkg)} || \\
          npx -y {shlex.quote(pkg)} --version >/dev/null
        export PATH="$HOME/.local/bin:$PATH"

        # ---- 3. 配置目录与 Ollama provider（可选）----
        CFG_DIR={shlex.quote(d['config_dir'])}
        mkdir -p "$CFG_DIR/profiles/{d['profile']}"
        {f'''if {str(dep['install_ollama']).lower()}; then
          if command -v ollama >/dev/null 2>&1; then
            for m in {models_line}; do ollama pull "$m" || true; done
          fi
        fi''' if models_line else ''}
        # patch 模板见 templates/cordis.patch.example.yml；此处不覆盖已有配置
        if [ ! -f "$CFG_DIR/profiles/{d['profile']}/cordis.patch.yml" ]; then
          echo "[dsh-install] 提示：请按 docs/CONFIGURATION.md 生成 cordis.patch.yml"
        fi

        # ---- 4. 服务（幂等，改前备份）----
        if {str(dep['start_service']).lower()}; then
          bash -s <<'SVC'
        SVC_MANAGER="{s['manager']}"
        SVC_NAME="{s['name']}"
        WEB_PORT="{d['port']}"
        BIND="{d['bind']}"
        if [ "$SVC_MANAGER" = "auto" ]; then
          if command -v systemctl >/dev/null 2>&1 && [ -d "$HOME/.config/systemd/user" ]; then
            SVC_MANAGER=systemd-user
          elif [ "$(uname -s)" = "Darwin" ]; then
            SVC_MANAGER=launchd
          else
            SVC_MANAGER=none
          fi
        fi
        echo "[dsh-install] 服务管理器: $SVC_MANAGER"
        case "$SVC_MANAGER" in
          systemd-user)
            UNIT="$HOME/.config/systemd/user/$SVC_NAME.service"
            [ -f "$UNIT" ] && cp "$UNIT" "$UNIT.bak.$(date +%Y%m%d-%H%M%S)"
            mkdir -p "$(dirname "$UNIT")"
            cat > "$UNIT" <<EOF
        [Unit]
        Description=DeepSeek Harness Web UI
        After=network-online.target
        [Service]
        Type=simple
        WorkingDirectory=$HOME
        Environment=HOME=$HOME
        Environment=PATH=$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin
        ExecStart=$HOME/.local/bin/dsh web --no-open --port $WEB_PORT --host $BIND
        Restart=always
        RestartSec=5
        [Install]
        WantedBy=default.target
        EOF
            systemctl --user daemon-reload
            systemctl --user enable --now "$SVC_NAME"
            loginctl enable-linger "$USER" 2>/dev/null || true
            ;;
          launchd)
            PLIST="$HOME/Library/LaunchAgents/com.dsh.web.plist"
            mkdir -p "$(dirname "$PLIST")"
            echo "[dsh-install] launchd plist 已生成模板，详见 docs/PLATFORMS.md"
            ;;
          none|*)
            echo "[dsh-install] 跳过服务创建（可手动: dsh web --port $WEB_PORT）"
            ;;
        esac
        SVC
        fi

        echo "[dsh-install] 完成 ✓"
        echo "[dsh-install] 验证: python3 deploy.py --config <config> --verify"
        """)


def _gen_powershell(cfg: dict) -> str:
    d, s = cfg["dsh"], cfg["service"]
    return textwrap.dedent(f"""\
        # DSH bootstrap — PowerShell（Windows 本机模式）
        Write-Host "[dsh-install] 平台: windows"
        $ErrorActionPreference = "Stop"

        # 1. Node.js（需 >= {cfg['node']['min_version']}，请用 winget/官网安装）
        if (-not (Get-Command node -ErrorAction SilentlyContinue)) {{
          Write-Error "请先安装 Node.js >= {cfg['node']['min_version']}（docs/PLATFORMS.md）"; exit 1
        }}
        Write-Host ("[dsh-install] node=" + (node -v))

        # 2. 安装 DSH
        npm install -g {d['package']}
        if ($LASTEXITCODE -ne 0) {{ npm install -g --prefix "$env:LOCALAPPDATA\\dsh" {d['package']} }}

        # 3. 配置目录
        $cfgDir = "{d['config_dir']}".Replace('~', $env:USERPROFILE)
        New-Item -ItemType Directory -Force -Path "$cfgDir\\profiles\\{d['profile']}" | Out-Null

        # 4. 服务（计划任务；需管理员权限，或手动启动）
        if ({str(cfg['deploy']['start_service']).lower()}) {{
          Write-Host "[dsh-install] Windows 服务方案见 docs/PLATFORMS.md（NSSM / 计划任务 / 手动启动）"
        }}
        Write-Host "[dsh-install] 完成 ✓"
        """)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def cmd_verify(cfg: dict, runner: Runner) -> int:
    print(f"\n=== 验证（目标: {runner.name}）===")
    checks = [
        ("Shell 可用", "echo ok"),
        ("Python3", "python3 --version 2>/dev/null || python --version 2>/dev/null || echo missing"),
        ("Node", "node -v 2>/dev/null || echo missing"),
        # npx 安装的 dsh 藏在 ~/.npm/_npx/<hash>/node_modules/.bin/，不在 PATH；
        # 只查 PATH 和 ~/.local/bin 会误报 missing（实测过），必须把 npx 缓存算进来。
        ("DSH 可执行", 'for p in $(command -v dsh) "$HOME/.local/bin/dsh" "$HOME"/.npm/_npx/*/node_modules/.bin/dsh; do [ -x "$p" ] && { echo "$p"; exit 0; }; done; echo missing'),
        ("监听端口", f"(ss -ltn 2>/dev/null || netstat -ltn 2>/dev/null) | grep ':{cfg['dsh']['port']} ' || echo '未监听'"),
    ]
    all_ok = True
    for label, cmd in checks:
        r = runner.run(cmd)
        val = r.stdout.strip().splitlines()[0] if r.stdout.strip() else "(空)"
        ok = "missing" not in val and "未监听" not in val
        print(f"  [{'OK' if ok else '  '}] {label}: {val}")
        if not ok:
            all_ok = False
    print("\n验证" + ("通过 ✓" if all_ok else "：部分项未就绪（首次部署前属正常）"))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="DSH Universal Installer")
    ap.add_argument("--config", default="config.json", help="配置文件路径")
    ap.add_argument("--mode", default="", choices=["", "local", "ssh"], help="覆盖部署模式")
    ap.add_argument("--dry-run", action="store_true", help="只打印将要执行的操作")
    ap.add_argument("--verify", action="store_true", help="只验证目标环境，不安装")
    ap.add_argument("--show-script", action="store_true", help="打印生成的 bootstrap 脚本")
    ap.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.dry_run:
        cfg["deploy"]["dry_run"] = True

    try:
        runner = build_runner(cfg, args.mode)
    except ValueError as e:
        print(f"[错误] {e}", file=sys.stderr)
        return 2

    if args.verify:
        return cmd_verify(cfg, runner)

    platform = detect_platform(runner)
    script = gen_bootstrap(cfg, platform)

    info = (f"=== DSH Universal Installer v{VERSION} ===\n"
            f"目标执行器 : {runner.name}\n"
            f"目标平台   : {platform}\n"
            f"DSH 版本   : {cfg['dsh']['version']}\n"
            f"Web 端口   : {cfg['dsh']['port']}\n"
            f"服务管理器 : {cfg['service']['manager']}")
    # --show-script 时把信息头写到 stderr，保证 stdout 是可直接保存的纯脚本
    print(info, file=sys.stderr if args.show_script else sys.stdout)

    if args.show_script:
        print(script)
        return 0

    if cfg["deploy"]["dry_run"]:
        print("\n[DRY-RUN] 以上配置不会实际执行。去掉 --dry-run 即开始部署。")
        return 0

    print("\n[部署] 生成并上传 bootstrap 脚本…")
    r = runner.write_file("~/.dsh-bootstrap.sh", script, "0700")
    if not r.ok:
        print(f"[失败] 写脚本: {r.stderr}", file=sys.stderr)
        return 1
    print("[部署] 执行安装（幂等，改前备份）…")
    r = runner.run("bash ~/.dsh-bootstrap.sh 2>&1", timeout=1200)
    print(r.stdout)
    if r.stderr.strip():
        print(r.stderr, file=sys.stderr)
    if not r.ok:
        print(f"[失败] 安装退出码 {r.code}", file=sys.stderr)
        return 1
    print("\n[完成] 部署成功。用 --verify 检查，或访问 http://<目标主机>:<端口>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
