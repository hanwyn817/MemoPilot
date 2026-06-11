# MemoPilot

MemoPilot 是一个面向个人和小团队的企业会议纪要生成工具。

新版设计不再解析 PDF、不做 RAG 检索、不预设风格词库。用户在网页中手工录入已经定稿的历史会议纪要纯文本，并可为样例标注标签。每次生成时系统把所选标签命中的历史纪要样例和本次会议原始记录一起放入大模型上下文，由模型直接从历史样例中学习格式、用词和行文风格。

## 启动

```bash
uv sync --extra dev
cp .env.example .env
uv run streamlit run app.py
```

`.env` 示例：

```bash
OPENAI_API_KEY=你的 DeepSeek API Key
OPENAI_BASE_URL=https://api.deepseek.com
MEMOPILOT_MODEL=deepseek-v4-pro
MEMOPILOT_HISTORY_FILE=data/history_minutes.json
```

## 使用方式

1. 在“历史纪要库”中录入历史会议主题、标签和已经成型的会议正文。
2. 已保存的历史样例可在管理区单条修改标签，也可给当前筛选结果批量追加标签；“标签管理”中可查看标签样例数，并执行标签重命名、合并和删除。
3. 在“生成纪要”中选择一个或多个历史样例标签；不选择标签时使用全部历史样例。
4. 输入本次会议主题和原始记录，页面会显示当前标签范围命中的样例数、将使用的历史样例预览，并按这些样例计算预计输入 tokens。
5. 点击生成，系统会通过一次大模型请求生成正式会议纪要正文。

生成页会展示 token 构成，包括系统提示、写作规则、历史样例和本次会议原始记录。生成结果保存为 TXT 时，会同时写入同名 `.metadata.json`，记录模型、所选标签、实际使用的历史样例 ID、预计输入 tokens 和输出 tokens，方便后续追溯。

历史纪要数据默认保存到 `data/history_minutes.json`，该文件已加入 `.gitignore`，避免把企业资料提交到 git。
