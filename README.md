# arXiv Weekly Digest（静态站 + GitHub Actions）

把 arXiv 每个方向的最新文献自动做成**中英对照网页**：抓取 → LLM 翻译 → LLM 总结/深读 → 生成静态站 → 推送到本仓库 → GitHub Pages 在线浏览。

## 目录结构

```
config.yml                     # 方向、窗口、LLM 端点/模型（不含 key）
scripts/
  summarize.py                 # OpenAI 兼容客户端（翻译/总结/深读）
  fetch_arxiv.py               # 抓取（读 config.yml 的 topics）
  translate.py                 # 并行翻译（线程池，断点续传）
  review.py                    # 自动选题 + 生成趋势与深读
  build_site.py                # 生成 docs/*.html
.github/workflows/weekly.yml   # 每周定时 + 手动触发，自动 commit & push
docs/                          # 站点根目录（GitHub Pages 用），含 data/*.json
```

## 本地跑一次

```bash
pip install pyyaml
# 配置 API（任一方式）：环境变量 LLM_API_KEY，或工作目录 keys.txt
export LLM_API_KEY=你的key           # PowerShell: $env:LLM_API_KEY="..."
# 可选覆盖端点/模型：
export LLM_BASE_URL=https://api.llm.ustc.edu.cn/v1
export LLM_MODEL=deepseek-flash

python scripts/fetch_arxiv.py
python scripts/translate.py
python scripts/review.py
python scripts/build_site.py
# 打开 docs/index.html 预览
```

连通性自检：`python scripts/summarize.py selftest`

## 部署到 GitHub（一次性）

1. 新建仓库，把本目录所有文件推上去：
   ```bash
   git init && git add . && git commit -m "init"
   git branch -M main
   git remote add origin https://github.com/<你>/<仓库>.git
   git push -u origin main
   ```
2. **Settings → Secrets and variables → Actions**，新建：
   - `LLM_API_KEY`（必填）
   - `LLM_BASE_URL`（可选，默认 USTC）
   - `LLM_MODEL`（可选）
3. **Settings → Pages**：Source 选 `Deploy from a branch`，Branch 选 `main`，目录选 `/docs`。
   站点地址：`https://<你>.github.io/<仓库>/`
4. **Actions** 标签页 → 选 `Weekly arXiv Digest` → `Run workflow` 手动跑一次验证；之后每周一 UTC 00:00 自动运行。

## 配置

改 `config.yml`：
- `topics`：要覆盖的方向（physics / ai / chem / math）。
- `window_hours`：168 = 一周。
- `max_per_topic`：每个方向最多篇数（控制翻译量与费用）。
- `llm.base_url` / `llm.model`：任意 OpenAI 兼容端点。
- `deep_read_count`：综述深读篇数。

## 安全

- API key 只放在 **GitHub Secrets**，工作流通过环境变量注入；`config.yml`、`docs/` 里**绝不含 key**。
- Actions 用仓库自带 `GITHUB_TOKEN`（`permissions: contents: write`）提交，无需额外凭证。

## 说明

- arXiv 内容版权归原作者；本站仅做翻译与摘要的自动聚合，均附原文 arXiv/PDF 链接。
- 翻译/总结由 LLM 生成，可能有误，请以原文为准。
