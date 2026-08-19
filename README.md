# 金融长上下文推理与财报反欺诈数据说明

## 核心研究问题

如何利用 Agentic AI 组织财务报表、股东关系、风险公告和第三方研究观点，实现：

1. 对跨年度、跨报表的金融长上下文进行连续推理；
2. 从上市公司出发穿透股东关系，发现共同股东和潜在关联；
3. 结合财务异常与外部证据，形成可追溯的反欺诈问答；
4. 在回答中明确区分已确认事实、风险信号和待核实线索。

## 数据与研究问题的联系

| 目录 | 数据内容 | 规模 | 对核心问题的作用 |
| --- | --- | ---: | --- |
| `data/1` | 多轮金融问答 | 1,410 条，35 个会话 | 用于研究多轮上下文记忆和问题分解，但反欺诈问题较少，不能直接作为反欺诈测试集 |
| `data/2` | 上市公司前十大股东 | 约 64.6 万条 | 构建“股东持有上市公司”关系，支持共同股东发现和有限的股权穿透 |
| `data/3` | 风险类公告索引 | 7,311 条，覆盖 2,585 只证券 | 提供违规处罚、监管措施、担保、风险提示等外部证据入口 |
| `data/4` | 资产负债表、利润表、现金流量表 | 共 117,214 条 | 支持跨期比较、跨表勾稽和财务异常识别，是反欺诈分析的主体数据 |
| `data/5` | 券商公司研究报告摘要 | 55,214 条，覆盖 3,438 只证券 | 提供业绩解释、盈利预测和风险提示，用于与财报及公告交叉验证 |

## 各部分数据的组成与示例

### 1. 多轮问答数据（`data/1`）

一行表示某个会话中的一个用户问题。同一个 `session_id` 下的多行数据按顺序组成一段多轮对话。

| 字段 | 含义 |
| --- | --- |
| `session_id` | 会话编号，用于组织同一段上下文 |
| `question` | 用户提出的自然语言问题 |
| `think_flag` | 是否被标记为需要进一步推理 |

示例：

| session_id | question | think_flag |
| ---: | --- | --- |
| 1 | 今天市场上有哪些涨停的股票 | False |
| 1 | 今天自选股涨最多？ | True |
| 1 | 市场最新研报有哪些？ | True |

这些记录适合测试 Agent 是否能理解“今天”“自选股”“还有哪些”等依赖前文的表达，但需要补充专门的财报反欺诈问题。

### 2. 前十大股东数据（`data/2/上市公司前十大股东.xlsx`；原始表名：`clean.xlsx`）

一行表示“某位股东在某个截止日持有某家上市公司的股份”。同一公司、同一截止日的多行记录共同构成该期的前十大股东名单。

| 字段组 | 主要字段 | 含义 |
| --- | --- | --- |
| 上市公司 | `s_info_windcode`、`s_info_compcode` | 证券代码和公司 ID |
| 股东实体 | `s_holder_name`、`s_holder_aname` | 股东名称及标准名称 |
| 持股关系 | `s_holder_quantity`、`s_holder_pct` | 持股数量和持股比例 |
| 股份属性 | `s_holder_holdercategory`、`s_holder_sharecategoryname` | 股东类型及股份性质 |
| 时间 | `ann_dt`、`s_holder_enddate` | 公告日和持股截止日 |

简化示例：

| 上市公司 | 股东 | 截止日 | 持股数量 | 持股比例 | 股份性质 |
| --- | --- | ---: | ---: | ---: | --- |
| `300838.SZ` | 王秀国 | 2023-07-25 | 10,892,000 | 7.99% | 限售流通 A 股、A 股流通股 |
| `300838.SZ` | 任翔 | 2023-07-25 | 12,237,000 | 8.98% | A 股流通股 |

该结构可直接转化为“股东 -> 持有 -> 上市公司”的图谱边。若同一股东出现在多家公司中，可继续发现共同股东关系，但股东同名问题需要额外核验。

### 3. 风险公告数据（`data/3/公司风险公告目录.xlsx`；原始表名：`clean.xlsx`）

一行表示一篇上市公司公告的索引信息。每篇公告具有唯一 ID，并通过证券代码关联上市公司。

| 字段 | 含义 |
| --- | --- |
| `object_id` | 公告唯一标识 |
| `s_info_windcode` | 公告所属证券 |
| `ann_dt` | 公告日期 |
| `n_info_title` | 公告标题 |
| `n_info_fcode` | 公告类型代码，可能包含多个类型 |
| `n_info_annlink` | 公告 PDF 地址 |

示例：

| 证券代码 | 公告日期 | 标题 | 类型 |
| --- | ---: | --- | --- |
| `603439.SH` | 2026-05-26 | 关于公司最近五年被证券监管部门和交易所处罚或采取监管措施情况的公告 | 违纪违规、其他公告 |
| `600238.SH` | 2026-05-26 | 关于对行政监管措施决定书的整改报告 | 违纪违规 |

该数据用于证明公司是否发生过监管、处罚或整改事件。当前记录只保存标题和链接，若要回答处罚原因、责任人和整改内容，还需要取得并解析 PDF 正文。

### 4. 三张财务报表（`data/4`）

一行表示一家公司的某张报表在某个报告期的一组财务科目。三张表都通过 `s_info_windcode + report_period` 对齐。

| 文件 | 一行包含的主要内容 | 代表字段 |
| --- | --- | --- |
| 利润表 | 某报告期的收入、成本和利润 | `oper_rev`、`oper_profit`、`net_profit_excl_min_int_inc`、`rd_expense` |
| 资产负债表 | 报告期末的资产、负债和权益余额 | `monetary_cap`、`acct_rcv`、`inventories`、`tot_assets`、`tot_liab` |
| 现金流量表 | 某报告期内经营、投资和筹资现金流 | `net_cash_flows_oper_act`、`net_cash_flows_inv_act`、`net_cash_flows_fnc_act` |

利润表简化示例：

| 证券代码 | 公告日 | 报告期 | 营业收入 | 营业利润 | 净利润 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `920088.BJ` | 2026-04-30 | 2026-03-31 | 53,400,311.43 | 12,609,560.18 | 11,362,362.14 |

系统不会只看一个数字，而是把同一公司的多期数据连接成长序列，再把三张表进行交叉核验。例如，利润增长时同步检查经营现金流、应收账款和存货是否出现反向变化。

### 5. 券商研报数据（`data/5`）

一行表示一篇公司研究报告。结构化字段描述报告来源和评级，`abstract` 保存较长的正文摘要。

| 字段组 | 主要字段 | 含义 |
| --- | --- | --- |
| 报告身份 | `report_id`、`org_name`、`author` | 研报 ID、机构和作者 |
| 研究对象 | `sec_code`、`sec_name` | 证券代码和名称 |
| 报告分类 | `report_type`、`report_sub_type` | 公司研究、业绩点评、公司深度等 |
| 观点 | `rating_org`、`rating_change`、`tar_price` | 评级、评级变化和目标价 |
| 文本 | `title`、`abstract` | 研报标题及摘要 |
| 时间 | `write_date`、`publish_date` | 撰写日和发布日期 |

简化示例：

| 证券 | 机构 | 类型 | 评级 | 摘要包含的信息 |
| --- | --- | --- | --- | --- |
| 永兴股份（601033） | 东吴证券 | 业绩点评 | 买入、维持 | 营收、净利润、自由现金流、负债率、盈利预测及风险提示 |
| 金风科技（002202） | 东吴证券 | 业绩点评 | 增持、维持 | 毛利率、订单、现金流、盈利预测及行业风险 |

研报摘要可以解释财务变化，但属于分析师观点。系统应将其中的财务数字与正式报表核对，并将预测和评级单独标识，不能当作已确认事实。

## 数据之间的关联方式

主要关联键是证券代码和时间：

```text
上市公司（证券代码）
├── 财务报表：报告期、公告日、财务科目
├── 股东关系：股东名称、持股比例、持股截止日
├── 风险公告：公告类型、标题、公告日、PDF 链接
└── 券商研报：发布日期、摘要、评级、风险提示
```

一次反欺诈问答可按以下证据链展开：

```text
用户问题
  -> 确定公司与报告期
  -> 比较多期财务指标并进行三表核验
  -> 识别利润、现金流、应收、存货或负债异常
  -> 穿透主要股东并查找共同股东
  -> 检索监管公告和券商研报
  -> 输出异常依据、关系路径、外部证据及可信度
```

## 可重点研究的反欺诈信号

- 净利润增长，但经营活动现金流持续下降；
- 营业收入增长明显高于销售收现增长；
- 应收账款或存货增速长期高于收入增速；
- 利润过度依赖投资收益、公允价值变动或非经常性项目；
- 资产减值、信用减值在不同报告期大幅反转；
- 短期债务增加，但货币资金和偿债现金流恶化；
- 财务数据、监管公告与券商研报中的描述相互矛盾；
- 多家风险公司存在共同主要股东或异常持股变化。

## 当前数据边界

1. `data/2` 只有前十大股东，不包含完整的子公司、实际控制人和多层控制关系，因此只能进行有限穿透。
2. `data/3` 只有公告标题、分类和链接，没有公告正文，现阶段只能形成标题级证据。
3. `data/5` 是券商研报而非新闻、社交媒体等广义舆情，观点可能存在正向偏差。
4. 三张财务表的 `statement_type` 均为 `408006000`，按字段字典表示母公司报表，需要确认是否缺少合并报表。
5. 题目所述约 5,000 条测试集未在当前目录中出现；现有 1,410 条问答以行情和投顾问题为主。

## 初版系统定位

基于现有数据，初版更适合定位为“财务风险线索发现与证据问答系统”，而不是自动判定企业财务造假。系统输出应保留来源和时间，并将结论分为：

- **已确认事实**：监管处罚、公司公告等明确披露的信息；
- **高风险异常**：多项财务异常且存在外部证据支持；
- **待核实线索**：模型发现异常，但缺少公告或审计证据；
- **数据不足**：缺少正文、合并报表或完整股权链，无法可靠判断。

## SQLite 数据库与查询接口

`src/jrkj/database.py` 将 `data/2` 至 `data/5` 清洗到 `database/jrkj.sqlite3`。数据库包含以下六张表：

| SQLite 表 | 数据来源 | 主要索引 |
| --- | --- | --- |
| `shareholders` | `data/2` | `s_info_windcode + s_holder_enddate/ann_dt` |
| `announcements` | `data/3` | `s_info_windcode + ann_dt` |
| `financial_income` | `data/4` 利润表 | `s_info_windcode + report_period/ann_dt` |
| `financial_balance` | `data/4` 资产负债表 | `s_info_windcode + report_period/ann_dt` |
| `financial_cashflow` | `data/4` 现金流量表 | `s_info_windcode + report_period/ann_dt` |
| `research_reports` | `data/5` | `s_info_windcode + publish_date` |

日期统一保存为 `YYYYMMDD` 整数。研报原始数据中的证券代码会结合交易所字段转换为 Wind 格式，例如 `601033 + XSHG -> 601033.SH`。

安装本地项目并构建数据库：

```bash
cd JRKJ
python -m pip install -e .
jrkj build-db --force
```

Python 查询接口：

```python
from jrkj import (
    query_financial_statements,
    query_top_shareholders,
    query_shareholder_connections,
    query_risk_announcements,
    query_research_reports,
)

financials = query_financial_statements("920088.BJ", "2026-03-31", "2026-03-31")
shareholders = query_top_shareholders("600238.SH", limit=10)
connections = query_shareholder_connections("600238.SH", end_date="2026-03-31")
announcements = query_risk_announcements("600238.SH", start_date="2024-01-01")
reports = query_research_reports("601033.SH", limit=5)
```

也可以直接从命令行查询：

```bash
jrkj query financial 920088.BJ --start 2026-03-31 --end 2026-03-31
jrkj query shareholders 600238.SH --limit 10
jrkj query announcements 600238.SH --start 2024-01-01
jrkj query reports 601033.SH --limit 5
```

当前已用纯代码验证：`920088.BJ` 在 2026 年一季度的三张报表均可查到；其利润表营业收入为 53,400,311.43 元、营业利润为 12,609,560.18 元、净利润为 11,362,362.14 元。`600238.SH` 可查询到 2026-03-31 的主要股东及多条监管整改公告；`601033.SH` 可查询到带摘要的券商研报。

运行完整性测试：

```bash
conda activate jrkj
python -m unittest discover -s tests -v
```

项目目录职责如下：

```text
JRKJ/
├── src/jrkj/       可复用的数据库构建与查询代码
├── scripts/        独立运维工具，例如原始数据下载
├── tests/          自动化测试
├── data/           原始数据及字段字典
├── database/       清洗生成的 SQLite 数据库
├── README.md       项目与数据说明
├── SKILL.md        长期项目约定
└── pyproject.toml  Python 项目配置与依赖
```

下载工具从 `JRKJ_SFTP_USERNAME` 和 `JRKJ_SFTP_PASSWORD` 环境变量读取凭证，源码中不保存账号密码。

## 初版：证据约束的多表 Agent

根目录 [agent.py](agent.py) 实现了单 Agent、多工具的 ReAct 循环，使用开启 Thinking、`low` reasoning effort 的 `deepseek-v4-flash`。当前版本先采用可审计的工具编排，不强行拆分 Multi-Agent；模型负责规划，代码负责查询、计算和证据校验。当前工具协议包括：

1. `query_table`：按证券代码查询一张财务表、股东表、公告表或研报表；显式区分最近记录与指定时间范围，一次调用可返回多个报告期；
2. `calculate_ratio`：使用查表结果计算比率，避免模型自行心算；
3. `calculate_change` / `classify_series`：确定性完成差额、同比和趋势判断，并检查报告期口径；
4. `describe_limitation`：对公告正文、控制链、合并报表等数据边界返回可引用说明；
5. `finish_answer`：终止循环，并输出固定 JSON 模板。

一次任务允许查询多张表，最多 8 次数据查询和 10 个模型轮次。跨表问题必须分别取得所需报表，按报告期对齐后再计算；模型不能用一张表的结果替代另一张表。任务级 `TaskMemory` 去重当前问题的查询证据并保存中间计算；`PersistentEvidenceMemory` 将工具取得的结构化事实写入 `database/jrkj_memory.sqlite3`，支持跨问题复用。

长期记忆采用证据账本而不是模型摘要：每条记录保存公司、数据表、期间、字段值、原始 `_source` 和数据集版本。数据源数据库的大小或修改时间变化后会生成新版本，旧证据不会自动参与当前召回。记忆只能复用已经取得的事实，不能填补数据库中不存在的信息，也不能绕过公告正文、实控链或合并报表的数据边界。最终结果格式为：

```json
{
  "结论": "简洁的数据结论",
  "证据": [
    "事实描述；来源：database/jrkj.sqlite3#表名:证券代码与日期"
  ],
  "置信度": "high"
}
```

模型配置统一放在项目根目录 `.env`：

```dotenv
LLM_API_KEY=
LLM_BASE_URL=https://api.deepseek.com/beta
MODEL_NAME=deepseek-v4-flash
```

在 `LLM_API_KEY` 后填入本地 Key。后续新增模型相关配置也集中放在该文件；同名系统环境变量会覆盖 `.env` 中的值。

首次运行先安装项目依赖：

```bash
cd /home/dairuiqi/JRKJ
conda activate jrkj
python -m pip install -e .
```

如果 `database/jrkj.sqlite3` 已存在，可以直接运行 Agent：

```bash
python agent.py "920088.BJ 在 2026 年一季度的营业收入是多少？"
python agent.py "600238.SH 最新一期第一大股东及持股比例是多少？"
python agent.py "600238.SH 最新的风险公告是什么？"
```

不在命令后提供问题时，会进入交互输入模式：

```bash
python agent.py
```

如果数据库不存在或需要从原始数据重新生成：

```bash
jrkj build-db --force
```

运行离线测试不会调用模型 API，也不会产生费用：

```bash
python -m unittest discover -s tests -v
```

当前版本已经覆盖单表查询、跨期比较、三张财务报表的多表取数，以及基于股东名称的双向穿透。共同股东结果仅作为待核实线索，不能仅凭同名认定同一主体或关联关系。公告正文、实际控制链和合并报表仍属于数据边界，系统必须明确拒答；持久化公司记忆属于下一迭代。

### 长上下文 ContextBuilder

`src/jrkj/context.py` 提供确定性的长上下文构建器。它先从版本化证据账本中按证券代码和问题主题召回候选事实，再按数据表、报告期和来源稳定排序，并按 token 预算裁剪。注入模型的每条事实都保留原始数据库来源；召回为空或问题要求最新数据时，Agent 仍必须查询原始表。该设计避免把完整历史对话直接塞入上下文，也避免把模型摘要误当作事实。

长上下文分为三层：当前任务的工作记忆、跨问题的结构化证据记忆，以及可由财务/股东/公告/研报表重新查询的原始数据层。数据版本变化后旧证据自动隔离，保证长期记忆不会污染新一轮财务判断。

### 基线评测

`scripts/run_agent_evaluation.py` 将 `test.md` 中的参数化题型实例化为 19 条真实证券问题，并逐题保存结果。建议为不同架构使用不同文件名和批次：

```bash
conda activate jrkj
python -u scripts/run_agent_evaluation.py \
  --output evaluation/agent_error_analysis_thinking.csv \
  --batch phase1-thinking
```

产物位于：

- `evaluation/agent_error_analysis_thinking.csv`：包含参考答案、参考来源、Agent 回答、reasoning、工具轨迹、来源引用、置信度、Token 和人工标注列；
- `evaluation/agent_error_analysis_thinking.log`：按题目展开的易读运行日志；
- `evaluation/agent_error_analysis_non_thinking.csv/.log`：优化前保留的非 Thinking 基线。

CSV 的 `agent_思维链` 原样记录 DeepSeek API 返回的 `reasoning_content`，并穿插可复核的“工具名称、调用参数、工具返回”轨迹。Agent 会在后续工具轮次中回传 `reasoning_content`，以符合 Thinking Tool Calls 协议。`是否正确`、`错误类型`、`是否幻觉` 默认留空，由人工对照参考答案标注；API 或循环运行失败会直接在 `错误类型` 中记录为“运行错误”。
