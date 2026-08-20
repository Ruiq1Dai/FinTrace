# AGENTS.md — 比赛冲刺、系统目标与 Harness 执行准则

## 1. 项目最终要做成什么

本项目不是普通金融聊天机器人，也不是单纯的 RAG 系统。

最终目标是构建一个：

> **面向上市公司风险核查的可审计 Agentic AI 金融调查系统。**

系统应能够针对复杂金融问题，自主完成：

**问题理解 → 任务拆解 → 多源数据查询 → 财务计算 → 股权图谱穿透 → 财务异常检测 → 公告/研报交叉验证 → 证据组织 → 风险结论 → 多轮追问。**

任何新增功能都必须服务于这条主链路。

---

# 2. 完整系统应分为六层

## Layer 1：金融数据与知识层

包含：

* 财务报表
* 股东与股权关系
* 监管公告
* 券商研报
* 公司基础信息
* SQLite 数据库
* 金融知识图谱

SQLite 是结构化事实源，Knowledge Graph 用于表达公司、股东、控制人及关联主体之间的关系。

---

## Layer 2：金融查询与工具层

向 Agent 提供标准化工具，而不是允许模型直接操作数据库。

例如：

* FinancialQueryTool
* ShareholderQueryTool
* AnnouncementSearchTool
* ResearchSearchTool
* GraphTraversalTool
* RelatedPartyTool
* FinancialCalculatorTool

所有工具必须：

* 输入参数明确
* 输出结构化
* 可测试
* 可追溯
* 失败时返回明确原因

---

## Layer 3：确定性金融推理与图计算层

LLM 负责判断“需要算什么”，代码负责“真正计算”。

至少包括：

### 财务计算

* 同比
* 环比
* 差额
* 财务比率
* 趋势
* 收入与现金流背离
* 应收异常
* 存货异常
* 毛利率异常

### 图计算

* K-hop 股权穿透
* 实际控制人识别
* 两公司关系路径
* 共同股东
* 关联主体
* 环状持股检测

原则：

> 可以确定性计算的内容，不交给 LLM 猜。

---

## Layer 4：Agent 推理与长上下文层

Agent 负责：

1. 理解问题；
2. 拆分子任务；
3. 选择工具；
4. 根据中间结果继续调查；
5. 判断是否需要图谱穿透；
6. 判断是否需要进一步检索公告；
7. 组织最终答案。

包含：

* Planner
* Tool Router
* Context Manager
* Short-term Memory
* Persistent Evidence Memory
* Retry / Recovery

注意：

系统保存的是：

> Agent 决策轨迹、工具调用轨迹、结构化推理摘要。

不要把系统设计成暴露模型内部 Chain-of-Thought。

---

## Layer 5：Evidence 与可信分析层

这是本项目的重要特色。

每个重要结论尽量绑定：

* 数据来源
* 公司
* 报告期
* 原始字段
* 原始值
* 计算公式
* 图关系路径
* 公告来源
* 置信度
* 限制说明

最终形成：

**Claim → Evidence → Calculation / Graph Path → Source**

目标不是只给答案，而是让答案可以被审计。

---

## Layer 6：应用、评测与展示层

包括：

### Web Investigation Workbench

至少展示：

* 用户问题
* Agent Plan
* Tool Calls
* 财务趋势
* Knowledge Graph
* Evidence Chain
* Risk Conclusion

### Evaluation System

统一评测：

* Answer Accuracy
* Financial Calculation Accuracy
* Graph Path Accuracy
* Evidence Coverage
* Tool Success Rate
* Unsupported Claim Rate
* Context Reference Accuracy
* Latency

### Engineering Harness

保证：

* 项目能安装
* 数据库存在
* API 正常
* Graph 正常
* 测试正常
* Demo 正常

---

# 3. 三档系统目标

所有开发必须先保证低级目标，再升级高级目标。

禁止为了高级目标破坏已经可运行的低级目标。

---

# Level 0：最低可交付版本

如果时间严重不足，至少必须做到这一水平。

这是“能够正常参赛”的底线。

必须具备：

### 后端

* SQLite 金融数据库可查询
* Agent 能调用多个工具
* 财务确定性计算
* 基础股东查询
* 至少支持 1—3 跳股权关系
* Evidence 输出
* 基础 Memory
* `/api/analyze`

### 前端

必须是真实连接后端，而不是静态 Mock。

至少展示：

* Question
* Answer
* Tool Calls
* Financial Indicators
* Shareholder Graph
* Evidence
* Confidence / Limitations

### Demo

至少三个固定案例：

1. 财务趋势分析；
2. 股权穿透；
3. 综合风险分析。

### 工程

必须：

```text
pip install
↓
启动后端
↓
启动前端
↓
运行 Demo
```

提供：

* requirements.txt / pyproject.toml
* README
* QUICKSTART
* database
* smoke_test

### Evaluation

即使题量较少，也必须有：

* QA Accuracy
* Calculation Accuracy
* Graph Accuracy
* Evidence Coverage

**Level 0 的核心目标：稳定、真实、能跑。**

宁可功能少，也不能 Demo 是假的。

---

# Level 1：推荐的冲奖版本

这是 8 月 30 日前应优先达到的目标。

在 Level 0 基础上增加：

## Graph Intelligence

真正提供：

* K-hop 穿透
* Ultimate Controller
* Common Shareholder
* Related Path
* Circular Ownership

Graph 不能只是前端画图。

必须存在真正的图算法。

---

## Financial Fraud Signal Engine

至少覆盖：

* Revenue / Cash Flow Divergence
* Receivables Risk
* Inventory Risk
* Gross Margin Abnormality
* Related-party Risk
* Regulatory Risk

输出应称为：

> 财务异常或潜在欺诈风险线索

而不是直接认定“财务造假”。

---

## Agent Investigation Loop

Agent 可以根据中间发现继续调查。

例如：

```text
发现收入增长异常
↓
查询经营现金流
↓
发现现金流背离
↓
检查应收账款
↓
启动股权关系穿透
↓
发现关联路径
↓
查询监管公告
↓
形成交叉证据
```

这一过程是整个 Demo 的核心。

---

## Evidence-Centric Memory

Persistent Memory 不只是保存聊天。

应该优先保存：

> 已验证事实 + 来源 + 时间 + 实体 + Evidence ID。

后续问题优先复用已经确认的 Evidence。

---

## Evaluation Harness

至少建立：

```text
evaluation/
    dataset/
    baselines/
    runners/
    metrics/
    results/
```

比较：

* LLM Only
* Retrieval
* Retrieval + Calculation
* Retrieval + Calculation + Graph
* Full System

形成消融实验。

**Level 1 的核心目标：证明“为什么你的系统比普通 RAG 更强”。**

---

# Level 2：理想完整版

这是“不考虑时间、猛猛努力”的最终研究形态。

不要求 8 月 30 日前全部实现，但架构应允许未来扩展。

## 1. Hybrid Financial Knowledge System

从简单 NetworkX 扩展到真正图数据库：

* Neo4j / NebulaGraph 等
* 实体消歧
* Temporal Graph
* 股权关系时间变化
* 多类型金融关系

能够回答：

> “2022 年和 2024 年公司实际控制关系发生了什么变化？”

---

## 2. GraphRAG + Structured KG

形成双图体系：

### Structured Financial Graph

公司、股东、控制人、关系。

### Document Graph

公告、研报、财报段落及实体关联。

Agent 根据问题动态选择：

> SQL / Vector Retrieval / Knowledge Graph / Document Graph。

---

## 3. Advanced Fraud Reasoning

增加：

* Beneish M-Score
* Altman Z-Score
* Piotroski F-Score
* 行业 Benchmark
* Peer Comparison
* 时间序列异常
* Graph Risk Propagation

进一步形成：

> 多维风险因子 → 风险证据图 → Agent 综合判断。

---

## 4. Multi-Agent Investigation

只有 Level 1 完全稳定后才考虑。

例如：

```text
Planner Agent
Financial Analyst Agent
Graph Investigator Agent
Regulatory Evidence Agent
Verifier Agent
```

由 Orchestrator 管理。

但是：

**比赛冲刺期间禁止为了“Multi-Agent”标签强行拆 Agent。**

单 Agent + 高质量 Tools 通常比混乱的 Multi-Agent 更可靠。

---

## 5. Self-Evaluation Agent

回答完成后自动检查：

* 每个 Claim 是否有 Evidence
* 数字是否经过 Calculator
* 图谱关系是否真实存在
* 时间口径是否一致
* 是否存在 unsupported claim

如果发现问题：

> 自动回到查询阶段重新取证。

形成：

**Generate → Verify → Repair**

---

## 6. Full Observability

每次 Agent Run 保存：

* run_id
* query
* plan
* tool calls
* latency
* token usage
* evidence
* errors
* retries
* final answer
* metrics

最终形成真正的：

> Financial Agent Observability Platform。

---

# 4. Harness 思想

本项目采用：

> **Human Steering + Agent Execution + Machine Verification**

不是让 Codex 自由写代码。

而是把比赛目标转化为一个越来越严格的执行环境。

Codex 每完成一个任务，都必须经过 Harness。

---

## Engineering Harness

回答：

> “系统有没有被改坏？”

运行：

```text
pytest
smoke_test
api health check
database check
graph check
```

---

## Financial Correctness Harness

回答：

> “金融计算有没有算错？”

所有财务计算都应该有人工确认的小规模 Golden Cases。

例如：

```text
输入：
2023 Revenue = 100
2024 Revenue = 120

预期：
YoY = 20%
```

Codex 修改 `calculations.py` 后必须自动运行这些测试。

---

## Graph Harness

准备固定小图：

```text
A → B → C → D
```

已知：

* Ultimate Controller
* 2-hop path
* common shareholder
* circular relation

任何 Graph 修改必须通过这些 Golden Tests。

---

## Agent Harness

准备固定金融问题，例如：

> 分析公司收入和经营现金流变化。

预期 Agent 至少应该调用：

```text
financial_query
financial_calculator
```

而不是只检查最终文字。

Harness 要检查：

> Agent 是否走了正确的调查过程。

---

## Evidence Harness

对最终结果检查：

```text
Claim 有无 Evidence？
数字有无来源？
Graph Claim 有无 Path？
Calculation 有无 Formula？
```

形成：

> Unsupported Claim Rate。

---

# 5. 人工必须介入的事项

以下内容 Codex 不得自行决定：

1. 项目范围和优先级；
2. 金融业务规则；
3. 风险等级与阈值；
4. Ground Truth；
5. Demo 案例是否具有展示价值；
6. 实验结果是否可信；
7. 创新点表述；
8. 技术报告最终结论；
9. 是否进行重大架构重构；
10. 最终提交版本验收。

特别是：

> 数据异常 ≠ 财务欺诈。

Codex 不允许自行把异常指标解释为确定性欺诈结论。

---

# 6. 可以大量交给 Codex 的工作

包括：

* API 开发
* Graph 工具
* SQL Tool
* 前端组件
* 测试代码
* 数据 Schema
* Evaluation Runner
* 指标统计
* 图表生成
* README
* API 文档
* 技术章节初稿
* 重构
* 类型检查
* 错误处理
* Logging
* Smoke Test

推荐工作方式：

不是：

> “给我实现一个金融 Agent。”

而是：

> “读取 AGENTS.md 和当前代码。实现 K-hop 股权穿透。不要修改现有 SQLite Schema。先补 Golden Tests，再实现功能。完成后运行相关测试，并汇报修改文件、测试结果、遗留风险。”

---

# 7. 里程碑

## 8/20

目标：

**冻结整体设计。**

必须完成：

* 六层系统架构
* Evaluation 指标
* 报告目录

报告累计：

**约 5k 字**

---

## 8/21–22

目标：

**Graph + Fraud 核心能力。**

必须完成：

* Graph Traversal
* Controller / Related Path
* Financial Risk Signals
* 对应 Tests

报告累计：

**约 20k 字**

重点完成第 1—4 章。

---

## 8/23–24

目标：

**形成真正可以演示的完整系统。**

必须完成：

* `/api/analyze`
* 前后端真实连接
* Evidence Chain
* 4 个 Demo

报告累计：

**约 35k 字**

重点完成第 5—9 章主体。

---

## 8/25

目标：

**Feature Freeze。**

此后原则上不增加核心功能。

开始：

* Baseline
* Ablation
* Evaluation

报告累计：

**约 45k 字**

---

## 8/26

目标：

**可运行性。**

必须完成：

* Clean Install
* Offline Mode
* smoke_test
* Windows/Linux 基础验证

报告累计：

**约 55k 字**

---

## 8/27

目标：

**实验冻结。**

所有关键指标、图表、消融实验必须完成。

报告累计：

**约 65k 字**

---

## 8/28

目标：

**完整技术报告初稿。**

完成：

* Cases
* Innovation
* Limitations
* Conclusion

约：

**75k 字**

---

## 8/29

目标：

**形成正式提交作品。**

完成：

* 报告约 80k
* 参考文献
* 附录
* 精益画布
* Demo 材料
* 陌生环境测试

---

## 8/30

禁止增加功能。

只允许：

* Fix Bug
* Test
* Verify
* Package
* Submit

---

# 8. Codex 优先级原则

任何时候存在任务冲突，按照：

**可运行性 > 核心能力 > 实验数据 > 报告素材 > UI 美化 > 新功能**

判断。

在 Level 0 未稳定之前，禁止开发 Level 2 功能。

在 Level 1 未完成之前，禁止因为“技术先进”进行 Neo4j 迁移、Multi-Agent 重构、大规模模型微调等高风险改动。

比赛阶段追求的不是最大系统，而是：

> **一个完整闭环可以跑通、每项技术都有存在理由、关键能力都有实验支撑、每个重要结论都有证据来源的金融 Agent 系统。**

---

# 9. Codex 每次完成任务必须汇报

固定输出：

### Changes

修改了什么。

### Tests

运行了哪些测试以及结果。

### Evaluation Impact

是否影响任何比赛指标。

### Human Decisions Required

是否存在必须人工判断的问题。

### Milestone Status

当前里程碑完成度。

### Recommended Next Task

当前最应该继续做的一件事情。

不要主动扩大 Scope。
