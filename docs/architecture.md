# 需求阶段智能体集群 — 架构说明

## 整体架构

```
用户输入
  ↓
main.py（编排器）
  ↓
┌───────────────────────────────────────────────────────────────┐
│  阶段一        阶段二        阶段 2.5       阶段三             │
│  调研智能体 → 文档智能体 → PRD评审智能体 → 原型智能体        │
│  research     document     prd_review      prototype           │
└───────────────────────────────────────────────────────────────┘
  ↓                  ↓                               ↓
人工检查点①     人工检查点②                   阶段四：复盘智能体
                （含评审报告）                        ↓
                                               知识库（Chroma）
                                                     ↑
                                               下次项目开始时读取
```

---

## 文件职责说明

```
requirements-agent/
│
├── main.py                  编排器
│   职责：控制四个阶段的执行顺序、人工检查点、文件保存
│   不包含：任何业务逻辑或提示词
│
├── agent.py                 通用 agentic loop
│   职责：发送请求 → 处理 tool_use → 循环直到 end_turn
│   不包含：任何业务逻辑，可被所有智能体复用
│
├── prd_review_agent.py      PRD 评审智能体 ★ v2 新增
│   职责：从五个维度系统评审 PRD，输出分级问题清单
│   触发时机：文档智能体保存 PRD 后，原型智能体启动前，自动运行
│   五个维度：结构完整性 / 逻辑一致性 / 流程闭环 / 场景穷举 / 多角色协同
│
├── tool_handlers.py         工具实现层
│   职责：每个工具实际做什么（读文件、存数据、调外部API）
│   修改时机：接入真实外部系统时（Confluence、Jira、数据库等）
│
├── knowledge_base.py        长期记忆层
│   职责：向量数据库的读写，历史经验检索
│   底层：Chroma（本地）/ 可换 Pinecone（云端）
│
├── review_agent.py          复盘智能体
│   职责：对比访谈笔记和PRD，提炼经验，写入知识库
│   触发时机：每个项目完成后自动运行
│
├── prompts/                 提示词（唯一需要产品经理维护的目录）
│   ├── research_system.txt   调研智能体（v2 未改）
│   ├── document_system.txt   文档智能体（v2 升级：状态机章节、三类验收场景、强化 checklist）
│   └── prototype_system.txt  原型智能体（v2 升级：信息架构先行、场景必检清单、闭环约束）
│
├── tools/
│   └── definitions.py       工具 Schema（v2 新增 check_closure 工具）
│
├── examples/                历史项目示例（手动维护）
│
├── kb_data/                 知识库数据（自动生成，勿手动修改）
│
└── outputs/                 每次运行的产出（自动生成）
    └── 项目名_时间戳/
        ├── interview_notes.json
        ├── prd.md
        ├── prd_review_report.json   ★ v2 新增
        ├── prototype.html
        └── review.json
```

---

## 数据流

### 阶段间数据传递

```
调研智能体
  └─ save_interview_notes(JSON)
        ↓ 存入 state["interview_notes"]
文档智能体
  └─ get_interview_notes() 读取
  └─ save_prd(markdown)
        ↓ 存入 state["prd_document"]
PRD 评审智能体                        ★ v2 新增
  └─ 读取 state["prd_document"] + state["interview_notes"]
  └─ 输出结构化评审报告
        ↓ 存入 state["prd_review"]
原型智能体
  └─ get_prd() 读取 prd_document + prd_review（同时注入）
  └─ check_closure() 提交闭环自检（页面出口 + 场景覆盖）
  └─ save_prototype(html, closure_verified=true)
        ↓ 存入 state["prototype_html"]
```

关键设计：每个智能体只接收"上一阶段的结果"，不接收"上一阶段的对话历史"。
这保证了 context 不会随着阶段积累而膨胀。

PRD 评审报告的传递路径：`prd_review` 通过 `get_prd` 工具随 PRD 正文一并返回给原型智能体，
原型智能体的 `check_closure` 工具会校验评审中的 critical/major 问题是否都已在原型中覆盖。

### 知识库数据流

```
项目完成
  → review_agent 分析访谈笔记 vs PRD
  → 提炼 lessons_learned + missed_requirements
  → knowledge_base.save_project() 写入 Chroma

下次项目开始
  → search_knowledge_base 工具触发
  → knowledge_base.search_similar_projects() 语义搜索
  → 返回相似项目摘要 + 经验教训
  → 注入到调研智能体的当前 context
```

---

## 关键设计决策

### 为什么提示词单独放 .txt 文件

提示词的迭代频率远高于代码。产品经理可以直接改 `prompts/` 目录下的文件，不需要懂 Python。

### 为什么 context 不跨阶段传递

文档智能体不需要知道访谈的每一句话，只需要最终的结构化笔记。
原型智能体不需要知道 PRD 是怎么讨论出来的，只需要最终的 PRD 文本 + 评审摘要。
"只传结果，不传过程"保证了 context 可控。

### 为什么在原型之前加评审智能体，而不是原型之后

发现问题的成本随阶段递增：访谈修改 < PRD 修改 < 原型修改 < 开发后修改。
PRD 评审在低成本阶段拦截问题，避免原型带着结构性缺陷进入后续流程。
评审报告同时作为原型智能体的输入，驱动原型覆盖那些"在 PRD 里被发现但未显式描述"的场景。

### 为什么有 check_closure 工具

原型智能体在生成 HTML 后容易遗漏"空状态""操作后反馈""流程出口"等细节。
check_closure 工具将检查从提示词约束（模型自觉遵守）升级为工具调用（系统强制验证），
未通过检查时 save_prototype 直接报错拒绝，消除了依赖模型自律的不确定性。

### 为什么用向量数据库而不是直接把历史文件塞进 context

历史项目积累到 20 个后，全部塞进 context 会超 token 限制，且大量无关内容会干扰模型。
向量搜索只返回语义最相关的 3 个项目，精准且 token 消耗可控。

### 为什么有复盘智能体

人工很难每次都认真总结经验。复盘智能体强制在每个项目结束后自动运行，
保证知识库的持续积累不依赖人的自律性。

---

## 扩展指南

### 接入外部系统

只需修改 `tool_handlers.py`，其他文件不需要动：

```python
# 接入 Confluence
if tool_name == "save_prd":
    confluence.create_page(title=project_name, body=tool_input["prd_markdown"])

# 接入 Jira
if tool_name == "save_interview_notes":
    jira.create_epic(summary=project_name, description=tool_input["summary"])

# 接入飞书文档
if tool_name == "save_prd":
    feishu.create_doc(title=project_name, content=tool_input["prd_markdown"])
```

### 切换模型

在 `main.py` 的 `run_layer_one` 函数里改 `model=` 参数：

```python
# 换成 GPT-4o（通过 OpenRouter）
model="openai/gpt-4o"

# 换成免费模型测试
model="meta-llama/llama-3.3-70b-instruct:free"
```

### 升级向量数据库

当项目超过 100 个、需要多人共享知识库时，把 Chroma 换成 Pinecone：

```python
# knowledge_base.py 里替换 _get_client()
import pinecone
pinecone.init(api_key=os.environ["PINECONE_API_KEY"])
```

---

## 各智能体参数说明

| 智能体 | 模型 | temperature | max_tokens | 原因 |
|--------|------|-------------|------------|------|
| 调研 | claude-opus-4-5 | 0.3 | 4096 | 访谈需要推理能力强，轻微随机让提问更自然 |
| 文档 | claude-sonnet-4-6 | 0.1 | 8192 | PRD 要稳定一致，几乎不需要随机性 |
| PRD 评审 | claude-sonnet-4-6 | 0.1 | 4096 | 评审结论要客观一致，低温度减少误报 |
| 原型 | claude-sonnet-4-6 | 0.2 | 16384 | 代码生成要稳定，需要大 token 窗口 |
| 复盘 | claude-sonnet-4-6 | 0.2 | 2048 | 分析任务，稳定优先 |
