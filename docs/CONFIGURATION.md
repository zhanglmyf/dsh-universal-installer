# 配置参考

配置文件 `config.json`（从 `config.example.json` 复制）。所有值都是可选——未填时用内置默认。

## 优先级

`命令行参数 > 环境变量 DSH_* > config.json > 内置默认`

## 完整字段表

### deploy（部署行为）

| 字段 | 默认 | 说明 |
|---|---|---|
| `mode` | `local` | `local` / `ssh` |
| `install_node` | `true` | 是否自动装 Node.js |
| `install_ollama` | `false` | 是否拉取 Ollama 模型 |
| `start_service` | `true` | 是否创建并启动服务 |

### target（远程目标，仅 mode=ssh）

| 字段 | 默认 | 说明 |
|---|---|---|
| `host` | 空 | 主机名/IP（必填） |
| `user` | 空 | SSH 用户（留空用当前用户） |
| `port` | `22` | SSH 端口 |
| `ssh_key` | 空 | 私钥路径（留空用 agent/默认密钥） |
| `ssh_options` | 空 | 额外 ssh 参数，如 `-J jump.host` |

### dsh

| 字段 | 默认 | 说明 |
|---|---|---|
| `package` | `@deepseek-ai/dsh` | npm 包名 |
| `version` | `latest` | 版本号（固定更可复现） |
| `port` | `3080` | Web UI 端口 |
| `bind` | `127.0.0.1` | 监听地址 |
| `profile` | `web` | 配置 profile |
| `config_dir` | `~/.dsh` | 配置目录 |

### node

| 字段 | 默认 | 说明 |
|---|---|---|
| `min_version` | `24.9.0` | 最低版本 |
| `install_method` | `nvm` | `nvm` / `official` / `system` |

### ollama（可选：本地模型）

| 字段 | 默认 | 说明 |
|---|---|---|
| `base_url` | `http://127.0.0.1:11434` | Ollama API（须带端口） |
| `api_key_env` | `OLLAMA_API_KEY` | 存放 key 的环境变量名（Ollama 也需非空值） |
| `models` | `[]` | 要拉取的模型 id |
| `context_window` | `131072` | 上下文窗口，见排障 |
| `max_tokens` | `8192` | 最大输出 |

### service

| 字段 | 默认 | 说明 |
|---|---|---|
| `manager` | `auto` | `auto`/`systemd-user`/`launchd`/`windows-task`/`none` |
| `name` | `dsh-web` | 服务名 |
| `auto_start` | `true` | 开机自启 |

## 生成 cordis.patch.yml

DSH 的 provider / 模型配置写在 `~/.dsh/profiles/<profile>/cordis.patch.yml`（改这个，不要改只读的 `cordis.yml`）。接入本地 Ollama 的最小示例：

```yaml
- id: llm-pi-ai
  config:
    providers:
      local-ollama:
        displayName: Local Ollama
        apiKeyEnv: OLLAMA_API_KEY
        api: openai-completions
        baseURL: http://127.0.0.1:11434/v1
        models:
          - id: qwen3:8b
            name: Qwen3 8B
            contextWindow: 131072
            maxTokens: 8192
- id: agent-default-model
  config:
    provider: local-ollama
    model: qwen3:8b
```

**要点**：
- API 路径必须带 `/v1`
- `apiKeyEnv` 指向的环境变量必须非空
- Provider id 定下后别改（报错信息带它）
- 视觉模型（`input: [text, image]`）无 tools 能力，不能当 Agent 主模型

改完用 `dsh --profile <profile> --dump-config` 看真实生效值——这是唯一权威。
