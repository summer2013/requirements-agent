"""
工具定义：需求调研智能体集群（第一层）
所有工具 schema 集中在此文件，与 System Prompt 解耦。
修改工具定义无需改动提示词文件。
"""

# ─── 调研智能体工具 ────────────────────────────────────────
RESEARCH_TOOLS = [
    {
        "name": "search_knowledge_base",
        "description": (
            "搜索内部知识库，查找类似历史项目、行业最佳实践和竞品分析。"
            "在访谈开始前必须调用，了解背景信息。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词，例如：'电商平台库存管理' 或 '医疗SaaS用户权限'"
                },
                "search_type": {
                    "type": "string",
                    "enum": ["similar_projects", "industry_research", "competitive_analysis"],
                    "description": "搜索类型"
                }
            },
            "required": ["query", "search_type"]
        }
    },
    {
        "name": "ask_question",
        "description": (
            "向用户/产品负责人提一个访谈问题，等待用户回答。"
            "每次只问一个问题，收到回答后再决定下一个问题。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "访谈问题内容"
                },
                "phase": {
                    "type": "string",
                    "enum": ["background", "pain_points", "validation"],
                    "description": "当前访谈阶段"
                },
                "internal_note": {
                    "type": "string",
                    "description": "为什么问这个问题（内部备注，不展示给用户）"
                }
            },
            "required": ["question", "phase"]
        }
    },
    {
        "name": "save_interview_notes",
        "description": (
            "访谈完成后保存结构化笔记。"
            "只有在充分理解用户需求后才调用。调用此工具标志访谈结束。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_roles": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "role": {"type": "string"},
                            "description": {"type": "string"},
                            "technical_level": {
                                "type": "string",
                                "enum": ["低", "中", "高"]
                            },
                            "headcount": {"type": "integer"}
                        },
                        "required": ["role", "description"]
                    }
                },
                "pain_points": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "job": {"type": "string", "description": "用户任务描述"},
                            "current_solution": {"type": "string", "description": "现有解决方式"},
                            "pain": {"type": "string", "description": "具体痛点"},
                            "severity": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 10,
                                "description": "严重程度 1-10"
                            },
                            "frequency": {
                                "type": "string",
                                "enum": ["daily", "weekly", "monthly"],
                                "description": "发生频率"
                            }
                        },
                        "required": ["job", "pain", "severity"]
                    }
                },
                "requirements": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "feature": {"type": "string"},
                            "source_quote": {"type": "string", "description": "用户原话"},
                            "priority": {
                                "type": "string",
                                "enum": ["Must", "Should", "Could", "Won't"]
                            }
                        },
                        "required": ["feature", "priority"]
                    }
                },
                "success_metrics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "可量化的成功指标"
                },
                "open_questions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "还需进一步澄清的问题"
                },
                "summary": {
                    "type": "string",
                    "description": "200字以内的访谈总结，面向后续智能体"
                },
                "confidence_level": {
                    "type": "string",
                    "enum": ["high", "medium", "low"],
                    "description": "对需求理解的置信度"
                }
            },
            "required": ["user_roles", "pain_points", "requirements", "summary", "confidence_level"]
        }
    }
]

# ─── 文档智能体工具 ────────────────────────────────────────
DOCUMENT_TOOLS = [
    {
        "name": "get_interview_notes",
        "description": "读取需求调研智能体产出的结构化访谈笔记",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"}
            },
            "required": ["project_id"]
        }
    },
    {
        "name": "search_prd_templates",
        "description": "在知识库中搜索类似项目的 PRD 模板，用于参考结构和表达方式",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_type": {
                    "type": "string",
                    "description": "项目类型，例如：'电商'、'SaaS后台'、'移动App'"
                },
                "industry": {
                    "type": "string",
                    "description": "行业，例如：'零售'、'医疗'、'教育'"
                }
            },
            "required": ["project_type"]
        }
    },
    {
        "name": "save_prd",
        "description": "将完整的 PRD Markdown 文档保存到共享上下文",
        "input_schema": {
            "type": "object",
            "properties": {
                "prd_markdown": {
                    "type": "string",
                    "description": "完整的 Markdown 格式 PRD 文档"
                },
                "metadata": {
                    "type": "object",
                    "properties": {
                        "total_stories": {"type": "integer"},
                        "must_have_count": {"type": "integer"},
                        "total_story_points": {"type": "integer"},
                        "estimated_sprints": {"type": "number"}
                    }
                }
            },
            "required": ["prd_markdown"]
        }
    }
]

# ─── 原型智能体工具 ────────────────────────────────────────
PROTOTYPE_TOOLS = [
    {
        "name": "get_prd",
        "description": "读取 PRD 文档内容",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"}
            },
            "required": ["project_id"]
        }
    },
    {
        "name": "save_prototype",
        "description": "保存 HTML 原型文件",
        "input_schema": {
            "type": "object",
            "properties": {
                "html": {
                    "type": "string",
                    "description": "完整的单文件 HTML 原型代码"
                },
                "pages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "包含的页面列表"
                },
                "notes": {
                    "type": "string",
                    "description": "给评审者的说明"
                }
            },
            "required": ["html"]
        }
    }
]
