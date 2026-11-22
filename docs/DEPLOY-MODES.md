# 三种部署方式

`deploy.py` 把所有目标抽象成「执行器（Runner）」，所以本机 / 局域网 / 远程走的是同一套部署逻辑，区别只在 `deploy.mode` 和 `target`。

## 方式一：本机（local）

编排器直接在本机跑 subprocess。适合在你正在用的这台电脑上装 DSH。

```json
{ "deploy": { "mode": "local" } }
```

```bash
python3 deploy.py --config config.json
```

## 方式二：局域网（ssh，内网）

目标机是家里的 NAS、另一台 PC、内网服务器。前提：**SSH 免密已配好**。

```json
{
  "deploy": { "mode": "ssh" },
  "target": {
    "host": "nas.local",     // 或内网 IP
    "user": "your-user",
    "port": 22,
    "ssh_key": "~/.ssh/id_ed25519"
  }
}
```

一次性配免密：
```bash
ssh-keygen -t ed25519                       # 已有密钥可跳过
ssh-copy-id -i ~/.ssh/id_ed25519.pub your-user@nas.local
```

## 方式三：远程（ssh，经跳板 / 公网）

目标在公网或需经跳板机（bastion）。

```json
{
  "deploy": { "mode": "ssh" },
  "target": {
    "host": "server.example.com",
    "user": "your-user",
    "port": 22,
    "ssh_key": "~/.ssh/id_ed25519",
    "ssh_options": "-J jump.example.com -o ServerAliveInterval=60"
  }
}
```

`ssh_options` 会原样拼进 ssh 命令，`-J` 指定跳板机。等价于：
```bash
ssh -J jump.example.com your-user@server.example.com
```

## 三种方式的统一性

| 维度 | local | ssh（局域网） | ssh（远程） |
|---|---|---|---|
| 执行器 | LocalRunner | SSHRunner | SSHRunner |
| 命令传输 | subprocess | ssh + stdin | ssh + stdin |
| 文件写入 | 直接写 | base64 + ssh | base64 + ssh |
| bootstrap 脚本 | 同一份 | 同一份 | 同一份 |
| 幂等/备份 | 一致 | 一致 | 一致 |

**关键点**：无论部署到哪，生成的安装脚本、服务配置、目录结构完全一致。换目标只改配置，不改脚本。

## 网络受限时

- npm 拉包慢：给目标机配 registry 镜像（`npm config set registry https://...`）
- SSH 连不上：确认 `BatchMode=yes` 能免密（`ssh -o BatchMode=yes user@host echo ok`）
- 端口非 22：改 `target.port`
