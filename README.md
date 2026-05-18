# MemoPilot

MemoPilot 是一个面向个人和小团队的企业会议纪要生成工具。

新版设计不再解析 PDF、不做 RAG 检索、不预设风格词库。用户在网页中手工录入已经定稿的历史会议纪要纯文本，每次生成时系统把全部历史纪要样例和本次会议原始记录一起放入大模型上下文，由模型直接从历史样例中学习格式、用词和行文风格。

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

1. 在“历史纪要库”中录入历史会议主题和已经成型的会议正文。
2. 在“生成纪要”中输入本次会议主题和原始记录。
3. 点击生成，系统会通过一次大模型请求生成正式会议纪要正文。

历史纪要数据默认保存到 `data/history_minutes.json`，该文件已加入 `.gitignore`，避免把企业资料提交到 git。
