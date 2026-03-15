# 需求阶段智能体集群

将一段项目简介，自动完成：需求调研访谈 → PRD 文档 → HTML 原型，每阶段有人工检查点。

## 目录结构

```
requirements-agent/
├── .env.example                ← API Key 配置模板
├── .gitignore
├── requirements.txt
│
├── agent.py                    核心 agentic loop（不需要改）
├── main.py                     编排器入口
├── tool_handlers.py            工具实现（接外部系统改这里）
├── review_agent.py             复盘智能体
├── knowledge_base.py           长期记忆（Chroma 向量库）
│
├── prompts/
│   ├── api/                    ← API 方案使用（有工具调用）
│   │   ├── research_system.txt
│   │   ├── document_system.txt
│   │   └── prototype_system.txt
│   └── projects/               ← Claude Projects 方案使用（无工具调用）
│       ├── research_system.txt
│       ├── document_system.txt
│       └── prototype_system.txt
│
├── tools/
│   └── definitions.py          工具 Schema（API 方案专用）
│
├── examples/
│   └── supply_chain_notes.json 历史项目示例
│
├── docs/
│   ├── architecture.md         架构说明
│   └── project_guide.md        Claude Projects 使用指南
│
├── kb_data/                    知识库数据（运行后自动生成，不提交 Git）
└── outputs/                    每次运行产出（不提交 Git）
```

---

## 快速开始（API 方案）

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，填入 ANTHROPIC_API_KEY 或 OPENROUTER_API_KEY

# 3. 运行（交互模式）
python main.py --interactive

# 4. 运行（命令行参数）
python main.py \
  --project-name "供应链可视化平台" \
  --brief "公司采购部门需要一个系统追踪供应商交货状态..."
```

### 输出文件

每次运行在 `outputs/` 目录下生成：

```
outputs/项目名_时间戳/
├── interview_notes.json   结构化访谈笔记
├── prd.md                 PRD 文档
├── prototype.html         可交互原型（浏览器直接打开）
└── review.json            复盘经验（自动写入知识库）
```

---

## Claude Projects 方案（无需代码）

适合个人偶尔使用，不需要 Python 环境。

详细步骤见 `docs/project_guide.md`，核心流程：

1. 在 claude.ai 新建 Project
2. 上传 `prompts/projects/` 下的三个文件
3. 粘贴 Instructions（见 project_guide.md）
4. 开始对话，每个阶段结束手动保存并上传产出文件

---

## 两种方案对比

| | API 方案 | Projects 方案 |
|--|--|--|
| 是否需要写代码 | 需要 Python 环境 | 不需要 |
| 阶段间数据传递 | 自动 | 手动上传文件 |
| 工具调用 | 支持（知识库搜索等） | 不支持 |
| 知识库 | 自动写入 Chroma | 手动维护文件 |
| 适合场景 | 高频 / 团队使用 | 个人偶尔使用 |

---

## API 提供商

支持两种，在 `.env` 里配置：

**Anthropic 直接 API**
- 申请：https://platform.claude.com/api-keys
- 模型：`claude-opus-4-5` / `claude-sonnet-4-6`

**OpenRouter**
- 申请：https://openrouter.ai/keys
- 优势：一个 Key 访问所有主流模型，有免费模型可用
- 模型名格式：`anthropic/claude-sonnet-4-6`、`openai/gpt-4o`
- 免费测试：`meta-llama/llama-3.3-70b-instruct:free`

---

## 人工检查点

流程中有两个强制人工检查点：

1. **访谈笔记确认**（调研完成后）
2. **PRD 评审**（文档生成后）

输入 `y` 通过，输入 `n` + 修订意见返回修订（最多 3 次）。

---

## 接入外部系统

只需修改 `tool_handlers.py`，其他文件不需要动：

```python
# 接入 Confluence 保存 PRD
if tool_name == "save_prd":
    confluence.create_page(title=project_name, body=tool_input["prd_markdown"])

# 接入飞书文档
if tool_name == "save_prd":
    feishu.create_doc(title=project_name, content=tool_input["prd_markdown"])
```

---

## License

Apache License 2.0 — 可自由使用、修改、分发，需保留版权声明。

## Contributing

欢迎提 Issue 和 PR，尤其是：
- 新行业的提示词优化（`prompts/` 目录）
- 新的 `examples/` 案例
- `tool_handlers.py` 的外部系统集成
