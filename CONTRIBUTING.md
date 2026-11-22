# 贡献指南

欢迎贡献！本项目目标是让 DSH 在**任何系统、任何位置**都能简单部署，保持跨平台与配置驱动。

## 贡献方式

- **报告问题**：用 GitHub Issues，附上平台（Linux/macOS/Windows）、部署方式（local/ssh）、`deploy.py --show-script` 的输出。
- **提交代码**：Fork → 分支 → PR，一个 PR 只做一件事。

## 开发约定

1. **纯标准库优先**：编排器不引入第三方依赖。
2. **配置驱动**：任何主机、端口、路径、版本必须来自配置，不得写死具体值。
3. **脱敏红线**：提交前跑 `python3 scripts/healthcheck.py`，确认无真实 IP / 主机 / 密钥 / 私人路径。
4. **幂等可回滚**：写目标机配置的逻辑必须可重复运行、改前备份。
5. **三种方式都要顾及**：改部署逻辑时，确认 local 和 ssh 两条路都不受影响。

## 本地检查

```bash
python3 -m py_compile deploy.py scripts/*.py
python3 scripts/healthcheck.py
```
