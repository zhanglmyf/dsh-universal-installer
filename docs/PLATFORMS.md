# 各平台适配说明

`deploy.py` 通过 `uname` 自动探测平台，生成对应的 bootstrap 脚本和服务配置。也可在配置里强制指定 `service.manager`。

## Linux

**没有官方桌面版**。官方支持的方式是 CLI / Web UI（`npx @deepseek-ai/dsh web`），也就是本项目部署的形态。网上所谓 Linux DEB / AppImage 桌面包均为第三方构建，不是 DeepSeek 官方产品。

**服务管理**：`systemd-user`（默认自动探测到）

- 单元文件：`~/.config/systemd/user/<name>.service`
- 必须开 linger，否则注销后服务停：
  ```bash
  loginctl enable-linger "$USER"
  ```
- 常用命令：
  ```bash
  systemctl --user status dsh-web
  systemctl --user restart dsh-web
  journalctl --user -u dsh-web -f
  ```

**Node 安装**：`node.install_method: nvm`，会自动装 nvm 并装指定版本。

**无 systemd 的发行版**（如 Alpine）：设 `service.manager: none`，手动 `dsh web --port 3080`。

## macOS

**官方桌面版**只支持 Apple Silicon（DMG，macOS 13+）；Intel Mac 没有官方桌面版，请用本项目的 CLI/Web 方式。桌面版自带 Node 运行时，与本节手动装 Node 的流程是两条独立路线，不要混用。

**服务管理**：`launchd`

- plist 放 `~/Library/LaunchAgents/`
- 当前版本生成 plist 模板，需按 `docs/CONFIGURATION.md` 补全后 `launchctl load`
- Node 推荐 nvm 或 Homebrew：
  ```bash
  brew install node
  ```

**注意**：macOS 默认 shell 从 zsh 起，nvm 需在 `~/.zshrc` 里初始化。

## Windows

**官方桌面版 vs 本项目**：DeepSeek 官方提供 Windows x64 桌面应用（EXE，Windows 10+，自带 Node）。它是图形客户端，不提供 `--patch` 启动参数，也不由本编排器管理。下面讲的是 **CLI/Web 版**的部署流程；需要模型 patch 注入时请用 CLI/Web 版，或把 patch 手工并入桌面版的 profile 配置。

**Node 安装**：用 winget 或官网安装包，需 ≥ 24.9.0：
```powershell
winget install OpenJS.NodeJS.LTS
```

**DSH 安装**：`npm install -g @deepseek-ai/dsh`，若全局目录无权限：
```powershell
npm install -g --prefix "$env:LOCALAPPDATA\dsh" @deepseek-ai/dsh
```

**服务方案**（三选一）：

| 方案 | 说明 |
|---|---|
| NSSM（推荐常驻） | `nssm install dsh-web "node" "...dsh web --port 3080"` |
| 计划任务 | 登录时启动，用 `schtasks /create /sc onlogon` |
| 手动 | 直接 `dsh web --port 3080` |

**远程到 Windows**：Windows 的 SSH 默认 shell 是 PowerShell；本项目 SSHRunner 走 `bash -s`，远程 Windows 需在目标机装 Git Bash / WSL，或改用本机模式生成 `.ps1` 手动执行。

## 平台差异速查

| 项 | Linux | macOS | Windows |
|---|---|---|---|
| Shell | bash | bash/zsh | PowerShell |
| 服务 | systemd-user | launchd | NSSM/计划任务 |
| Node 路径 | nvm/~/.local/bin | nvm/brew | Program Files |
| 配置目录 | ~/.dsh | ~/.dsh | %USERPROFILE%\.dsh |
| 端口占用检查 | ss/netstat | lsof/netstat | netstat |
