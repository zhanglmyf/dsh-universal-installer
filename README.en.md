# DSH Universal Installer

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)

[中文](README.md) | **English**

One config file to install [DeepSeek Harness](https://github.com/deepseek-ai) anywhere — locally, on your LAN, or on a remote server, across all major platforms.

## Features

- **Three targets, one interface**: local / LAN SSH / remote SSH (with jump host) via a unified Runner abstraction
- **Cross-platform**: Linux (systemd-user), macOS (launchd), Windows (Task Scheduler / NSSM)
- **Config-driven**: hosts, users, ports, versions and paths all come from `config.json` — no hardcoding
- **Idempotent & reversible**: safe to re-run, auto-backup before changes
- **Pure stdlib**: Python 3.9+ only, no `pip install` needed
- **Dry run**: preview with `--dry-run`, inspect generated script with `--show-script`

## DSH editions (read this first)

DeepSeek Harness (dsh) is still a developer preview. It ships in three forms; this project deploys form 2.

| Form | Platforms | Notes |
|---|---|---|
| **Official desktop app** | Windows x64 (EXE, Windows 10+), macOS Apple Silicon (DMG, macOS 13+) | GUI app with a bundled Node runtime. **No official desktop build for Intel Mac or Linux.** |
| **CLI / Web UI** (this project) | Linux, macOS (incl. Intel), Windows, WSL | `npx @deepseek-ai/dsh web`, default `http://127.0.0.1:3080`, needs Node.js >= 24.9.0. Supports `--patch` injection. |
| **Mobile** | No official native app | There is no official DSH iOS/iPadOS/Android client. Use a browser to reach the Web UI (LAN or authenticated tunnel). The App Store app "DeepSeek – AI Assistant" is a chat assistant, **not Harness**, and sessions are not shared. |

Version notes: the npm package `@deepseek-ai/dsh` and desktop installers use **different version schemes** — never copy a desktop version into `config.json`. Linux DEB/AppImage "DSH Desktop" builds found online are community distributions, not official DeepSeek products. Windows users who want the official GUI should install the EXE directly; this project is for the always-on CLI/Web form.

## Quick start

```bash
cp config.example.json config.json
python3 deploy.py --config config.json --dry-run      # preview
python3 deploy.py --config config.json                 # deploy
python3 deploy.py --config config.json --verify        # verify
```

Set `deploy.mode` to `local` (this machine) or `ssh` (fill in `target` for LAN/remote).

## Docs

- [Deploy modes](docs/DEPLOY-MODES.md)
- [Platform notes](docs/PLATFORMS.md)
- [Configuration](docs/CONFIGURATION.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

## License

MIT.
