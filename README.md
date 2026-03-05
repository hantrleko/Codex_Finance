# Finance & Economics Daily Digest (P0)

这个项目会每天自动抓取公开金融/经济学文献，并生成类似 AI Digest 风格的日更内容（JSON + Markdown + HTML）。

## 当前能力（P0）

- 主源：OpenAlex 当日经济学文献。
- 备用源：当 OpenAlex 为空时，自动回退到 arXiv（q-fin/econ）。
- 摘要：
  - 默认规则化中文摘要。
  - 可选接入 OpenAI 兼容接口（`/chat/completions`）生成中文摘要。
- 质量闸门：当日抓取为 0 且历史 `latest` 有有效内容时，**不覆盖 latest**。
- 质量筛选：支持可配置主题白名单/黑名单 + 最低质量分，自动去重并剔除噪声条目。
- 告警落盘：空结果时写入 `output/alerts/YYYY-MM-DD.json`。
- 自动化：GitHub Actions 每天定时运行并提交 `output/` 结果。

## 快速开始

```bash
python src/digest.py
```

查看输出：

- `output/latest/digest.md`
- `output/latest/index.html`
- `output/YYYY-MM-DD/digest.json`

## 环境变量

- `DIGEST_MAX_PAPERS`：每期最多论文数（默认 12）
- `DIGEST_MIN_CITATIONS`：最小引用门槛（默认 0）
- `DIGEST_OUTPUT_DIR`：输出目录（默认 `output`）
- `DIGEST_KEEP_LATEST_WHEN_EMPTY`：空结果是否保留 latest（`1`/`0`，默认 `1`）
- `DIGEST_TOPIC_WHITELIST`：相关主题关键词白名单（逗号分隔，默认内置 finance/econ 词表）
- `DIGEST_TOPIC_BLACKLIST`：噪声关键词黑名单（逗号分隔，默认内置 spam 词表）
- `DIGEST_MIN_QUALITY_SCORE`：最低质量分（默认 2，分数越高越严格）

### 可选 LLM 摘要配置

- `LLM_API_BASE`：例如 `https://api.openai.com/v1`
- `LLM_API_KEY`
- `LLM_MODEL`：例如 `gpt-4o-mini`
- `LLM_TIMEOUT_SECONDS`：默认 30

> 若未配置 LLM 变量，系统会自动退回规则化摘要。


### 邮件推送（方案A：SMTP）

工作流会在日报生成后尝试发送邮件到 `yuchenhan2023@gmail.com`。
请在 GitHub 仓库 **Settings -> Secrets and variables -> Actions** 配置：

- `SMTP_HOST`
- `SMTP_PORT`（可选，默认 587）
- `SMTP_USER`
- `SMTP_PASS`

> 若未配置上述 SMTP Secrets，邮件步骤会自动跳过，不影响日报文件生成。
