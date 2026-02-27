# Finance & Economics Daily Digest (MVP)

这个项目会每天自动抓取公开金融/经济学文献，并生成类似 AI Digest 风格的日更内容（Markdown + HTML）。

## 已实现能力

- 从 OpenAlex 拉取当天发布的经济学文献（可扩展到更多来源，当前实现仅用 Python 标准库）。
- 自动抽取基础信息：标题、作者、来源、主题、链接、引用数。
- 自动生成中文简述（当前为规则化摘要，后续可接入 LLM）。
- 输出：
  - `output/YYYY-MM-DD/digest.json`
  - `output/YYYY-MM-DD/digest.md`
  - `output/YYYY-MM-DD/index.html`
  - `output/latest/*`（最新一期）
- 配置了 GitHub Actions 定时任务，每天自动生成并提交新一期。

## 快速开始

```bash
pip install -r requirements.txt
python src/digest.py
```

执行后查看：

- `output/latest/digest.md`
- `output/latest/index.html`

## 可配置参数

通过环境变量控制：

- `DIGEST_MAX_PAPERS`：每期最多论文数（默认 12）
- `DIGEST_MIN_CITATIONS`：最小引用门槛（默认 0）
- `DIGEST_OUTPUT_DIR`：输出目录（默认 `output`）

## 下一步建议

1. **接入 LLM 摘要与点评**：将 `_simple_zh_summary` 替换为模型调用。
2. **增加来源**：例如 NBER/IMF/BIS/OECD 的公开工作论文源。
3. **主题路由**：按资产定价、宏观金融、公司金融等栏目生成子榜单。
4. **部署站点**：配合 GitHub Pages 或 Vercel 自动发布 `output/latest/index.html`。
