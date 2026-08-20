# JRKJ Financial Investigation Agent

JRKJ 是一个面向上市公司风险核查的可审计金融调查系统。它让 Agent 通过标准化工具查询财务报表、股东关系、监管公告和研报，使用确定性代码完成财务计算与图遍历，并将结论绑定到可追溯证据。

系统输出的是财务异常或潜在风险线索，不把数据异常直接认定为财务欺诈。

## 主要功能

- SQLite 财务、股东、公告和研报查询
- 同比、趋势、比率与跨报表异常检测
- 共同股东、K-hop 路径、控制人候选和环状持股分析
- 公告正文与实体关联的文档图检索
- Claim、Evidence、Calculation、Graph Path 审计链
- 结构化证据记忆、运行轨迹和自检修复
- `/api/analyze` 与 Web Investigation Workbench
- 完整数据、图谱、风险策略和消融评测 Harness

## 项目结构

```text
JRKJ/
├── src/jrkj/          # 核心 Python 包
├── agent.py           # Agent 命令行入口与工具编排
├── main.py            # Web Workbench 统一启动入口
├── scripts/           # 数据构建、迁移、评测与 Smoke 脚本
├── tests/             # 自动化与 Golden Tests
├── frontend/          # 无构建工具的 Web 前端
├── data/              # 原始数据与可审计样本
├── database/          # 本地 SQLite 运行文件，不提交 Git
├── evaluation/        # 数据集、协议与评测结果
├── examples/          # 可直接运行的演示问题
└── docs/              # 风险策略与技术文档
```

各数据目录、评测产物和扩展文档说明见 [`data/README.md`](data/README.md)、[`evaluation/README.md`](evaluation/README.md) 与 [`docs/README.md`](docs/README.md)。

## 环境要求

- Python 3.10+
- Conda（推荐）
- SQLite 数据文件或构建数据库所需的源数据
- LLM 兼容的 Chat Completions API（运行 Agent 时需要）
- Neo4j 5.x（完整图谱验证需要）

## 安装

```bash
conda create -n jrkj python=3.10 -y
conda activate jrkj
python --version

# 仅当 Linux shell 仍错误指向旧的 base Python 时执行：
# export PATH="$CONDA_PREFIX/bin:$PATH" && hash -r

python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e . --no-deps

cp .env.example .env
```

在 `.env` 中填写本地 API Key。`.env` 已被 Git 忽略，不要提交密钥。

如果已提供 `database/jrkj.sqlite3`，可以直接运行；否则在所需源数据就位后构建：

```bash
jrkj build-db --force
```

`database/jrkj.sqlite3` 约 450 MB，属于本地运行资产，未纳入 Git。纯 clean clone 可以安装代码并运行数据契约、Smoke 和评测脚本；需要完整执行查询/记忆测试时，先提供该数据库或按上面的命令重新构建。

## 配置

常用环境变量如下，完整模板见 [`.env.example`](.env.example)。

| 变量 | 用途 | 必需条件 |
| --- | --- | --- |
| `LLM_API_KEY` | 模型服务密钥 | 运行 Agent |
| `LLM_BASE_URL` | Chat Completions API 地址 | 运行 Agent |
| `MODEL_NAME` | 模型名称 | 运行 Agent |
| `JRKJ_GRAPH_MODE` | `sqlite` 离线线索模式或 `neo4j` 图谱模式 | 图谱查询 |
| `NEO4J_URI` / `NEO4J_PASSWORD` | Neo4j 连接信息 | Neo4j 图谱模式 |

## 基本使用

启动 Web Workbench 与同源 API：

```bash
conda activate jrkj
python main.py --host 127.0.0.1 --port 8000
```

访问 <http://127.0.0.1:8000>，健康检查为 `GET /health`，分析接口为 `POST /api/analyze`。

直接运行单个调查问题：

```bash
python agent.py "600238.SH 2025 年与 2024 年相比，营业收入增长了多少？"
```

直接查询结构化数据：

```bash
jrkj query financial 600238.SH --start 2024-12-31 --end 2025-12-31
jrkj query shareholders 600238.SH --limit 10
```

更多固定问题见 [`examples/demo_questions.md`](examples/demo_questions.md)。

## 测试

以下命令不调用 LLM，也不会产生模型费用：

```bash
conda activate jrkj
python scripts/check_data.py --strict
python -m pytest -q
python scripts/smoke_test.py --skip-neo4j
python scripts/run_evaluation.py --skip-neo4j
```

离线模式不会验证真实 Neo4j 路径，不能作为完整图谱结果。

完整图谱验证需要先配置 Neo4j 并导入股东快照：

```bash
export JRKJ_GRAPH_MODE=neo4j
export NEO4J_URI=bolt://127.0.0.1:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD='your-local-password'
export NEO4J_DATABASE=neo4j

python scripts/migrate_ownership_to_neo4j.py
python scripts/smoke_test.py
python scripts/run_evaluation.py \
  --output evaluation/results/evaluation_live.json
```

正式评测还需遵循 [`evaluation/GROUND_TRUTH.md`](evaluation/GROUND_TRUTH.md) 的人工标注和复核要求。

## 数据与结论边界

- 前十大股东同名关系仅为待核实线索，不能自动证明主体同一或关联关系。
- 控制人结果是基于已验证图边的候选路径，不替代法律或审计判断。
- 研报预测属于分析师观点，不应作为已经发生的事实。
- 风险等级和阈值需由金融业务人员确认；异常信号不等于财务造假。
