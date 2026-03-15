# 需求阶段智能体集群 v2

从项目简介到可交互原型，全自动 + 人工检查点的 4 阶段流水线。

## 架构概览

```
用户输入项目简介
      │
      ▼
┌─────────────────┐
│  阶段 1          │  调研智能体（claude-opus）
│  需求调研访谈    │  → 知识库检索 → 结构化访谈 → 访谈笔记
└────────┬────────┘
         │  HITL 检查点①：确认访谈笔记
         ▼
┌─────────────────┐
│  阶段 2          │  文档智能体（claude-sonnet）
│  生成 PRD        │  → 读访谈笔记 → 生成含状态机的完整 PRD
└────────┬────────┘
         │  自动触发
         ▼
┌─────────────────┐
│  阶段 2.5        │  PRD 评审智能体（claude-sonnet）★ 新增
│  PRD 系统评审    │  → 5维度检查 → 结构化评审报告
└────────┬────────┘
         │  HITL 检查点②：确认 PRD + 评审报告
         │  （不通过 → 评审问题反馈给文档智能体修订）
         ▼
┌─────────────────┐
│  阶段 3          │  原型智能体（claude-sonnet）★ 升级
│  生成原型         │  → 信息架构 → 流程梳理 → HTML 原型
│                  │  → check_closure 闭环自检（新工具）
│                  │  → 通过后才能 save_prototype
└────────┬────────┘
         ▼
┌─────────────────┐
│  阶段 4          │  复盘智能体
│  复盘 & 知识库   │  → 提炼经验 → 写入向量知识库
└─────────────────┘
```

## 新增能力（v2 vs v1）

### ★ PRD 评审智能体（prd_review_agent.py）
在 PRD 生成后、原型制作前自动运行，从 5 个维度系统评审：

| 维度 | 检查内容 |
|------|---------|
| 结构完整性 | 背景/目标/角色/范围/异常是否齐全 |
| 逻辑一致性 | 前提/触发/结果/可逆性是否自洽 |
| 流程闭环 | 每个流程有出口，每个操作有反馈 |
| 场景穷举 | MECE 状态枚举，空态/异常/并发覆盖 |
| 多角色协同 | 跨角色流程、通知时机、等待态 |

评审结果分三级：**critical（必须修）/ major（原型前修）/ minor（后续迭代）**

### ★ PRD 文档智能体（升级）
- 新增**状态机章节**：对核心业务对象穷举所有状态 + 每种状态允许的操作
- 验收标准强制三类场景：主流程 + 异常流程 + 边界场景
- 新增 Out of Scope 强制声明
- 质量自检 checklist 覆盖：结构完整性 / 场景穷举 / 流程闭环 / 多角色协同

### ★ 原型智能体（升级）
- 新增工作顺序约束：**先信息架构 → 再流程梳理 → 最后生成 HTML**
- 新增 `check_closure` 工具：提交页面闭环自检报告，验证无死路、无缺失场景
- `save_prototype` 强制要求 `closure_verified: true`，未通过闭环检查不允许保存
- 每个页面必须实现：空状态 / 加载中 / 成功 / 错误 / 禁用 五种状态

### HITL 检查点升级
- **检查点①（访谈笔记）**：不变，显示角色/痛点/需求数量
- **检查点②（PRD + 评审）**：升级为展示完整评审报告，含 critical/major/minor 分级问题列表

## 文件结构

```
requirements-agent/
├── main.py                  # 编排器入口
├── agent.py                 # 核心 agentic loop（不变）
├── prd_review_agent.py      # ★ 新增：PRD 评审智能体
├── review_agent.py          # 复盘智能体（不变）
├── tool_handlers.py         # 工具处理器（新增 make_prototype_handler_v2）
├── knowledge_base.py        # 向量知识库（不变）
├── tools/
│   └── definitions.py       # 工具 schema（新增 check_closure 工具）
└── prompts/
    └── api/
        ├── research_system.txt   # 调研 prompt（不变）
        ├── document_system.txt   # ★ 升级：含状态机 + 强化 checklist
        └── prototype_system.txt  # ★ 升级：含闭环约束 + 场景必检清单
```

## 输出文件

每次运行在 `outputs/{project_name}_{timestamp}/` 下生成：

| 文件 | 说明 |
|------|------|
| `interview_notes.json` | 结构化访谈笔记 |
| `prd.md` | PRD 文档（含状态机） |
| `prd_review_report.json` | ★ 新增：PRD 评审报告（5维度问题清单） |
| `prototype.html` | 可交互低保真原型 |
| `review.json` | 复盘经验（已写入知识库） |

## 快速开始

```bash
# 安装依赖
pip install anthropic chromadb

# 配置 API Key
cp .env.example .env
# 编辑 .env，填入 ANTHROPIC_API_KEY

# 运行（交互模式）
python main.py --interactive

# 运行（命令行模式）
python main.py --project-name "订单管理系统" --brief "仓库团队需要管理发货订单..."
```

## 设计原则

- **PRD 先于原型**：评审报告在原型生成前完成，问题在低成本阶段发现
- **闭环强制验证**：原型 agent 必须通过 `check_closure` 工具验证才能保存
- **评审驱动修订**：人工不通过时，评审问题自动反馈给文档 agent，不需要手动描述
- **知识库积累**：每个项目的遗漏场景写入向量库，下次同类项目自动预警
