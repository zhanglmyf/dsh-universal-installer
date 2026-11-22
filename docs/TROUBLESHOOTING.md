# 排障速查

| 症状 | 原因 | 处理 |
|---|---|---|
| `spawn pnpm ENOENT` / `dsh: command not found` | 可执行文件不在 PATH | 把 `~/.local/bin` 加进 PATH；服务里要写 `Environment=PATH=...:/home/<user>/.local/bin` |
| 切换模型报 `MODEL_SWITCH_COMPACTION_FAILED` / headroom 报错 | compaction 默认 headroom 65536 不随窗口缩放，小窗口装不下 | 把模型的 `contextWindow` 调到 ≥131072 |
| 报错里 `reserves ... leaving no pressure budget` | 同上 | `131072 − maxTokens − 65536 > 0` 即可 |
| 视觉模型报 `does not support tools` | 视觉模型无工具能力 | 换普通文本模型当 Agent 主模型，视觉模型只做看图问答 |
| 服务重启后 PATH 丢失 | 手动 export 只影响当前 shell，不影响服务进程 | 系统服务单元里显式写 `Environment=PATH=...` |
| `systemctl --user` 报 connection refused | 没开 linger / 未登录图形会话 | `loginctl enable-linger "$USER"` |
| SSH 部署卡在认证 | BatchMode 下没有可用密钥 | 先 `ssh-copy-id` 配免密，再 `ssh -o BatchMode=yes user@host echo ok` 验证 |
| npm 拉包超时 | 网络受限 | 配 registry 镜像或代理 |
| 端口被占用 | 已有 dsh 实例 | 换 `dsh.port`，或停掉旧实例 |
| 多个 dsh 实例抢会话锁（"当前会话已被占用"） | 同时跑了两个 dsh web | 只保留一个实例，停掉另一个 |

## 验证生效配置的正确方法

```bash
dsh --profile web --dump-config
```

注意是 `--profile web --dump-config`（profile 级参数），不是 `dsh web --dump-config`（会报 unknown option）。

## 幂等与安全

- 所有写配置前会备份为 `*.bak-<时间戳>`
- `--dry-run` 只打印不执行；`--show-script` 打印完整生成的脚本供审阅
- 服务创建重复运行不会重复注册
