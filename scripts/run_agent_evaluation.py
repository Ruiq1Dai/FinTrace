#!/usr/bin/env python3
"""Run the concrete benchmark scenarios and create annotation-ready outputs."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from agent import MODEL_NAME, run_agent  # noqa: E402
from jrkj.investigation_run import InvestigationRun  # noqa: E402


def case(
    question_id: str,
    category: str,
    difficulty: str,
    company: str,
    question: str,
    reference_answer: str,
    reference_source: str,
    expected_confidence: str,
) -> dict[str, str]:
    return {
        "question_id": question_id,
        "question_content": question,
        "category": category,
        "difficulty": difficulty,
        "涉及公司代码": company,
        "参考答案": reference_answer,
        "参考数据来源": reference_source,
        "期望置信度分类": expected_confidence,
    }


CASES = [
    case("Q1", "单表/单跳", "Easy", "600238.SH", "600238.SH 在 2025-12-31 的营业收入和净利润分别是多少？", "母公司口径营业收入328,367,159.64元，净利润-8,713,696.22元。", "financial_income；600238.SH；report_period=20251231；oper_rev、net_profit_excl_min_int_inc", "high"),
    case("Q2", "单表/单跳", "Easy", "600238.SH", "截至 2026-03-31，600238.SH 的前十大股东中，持股比例最高的是谁，占比多少？", "海口市国有资产经营有限公司，持股13.48%。", "shareholders；600238.SH；s_holder_enddate=20260331；s_holder_name、s_holder_pct", "high"),
    case("Q3", "单表/单跳", "Easy", "600238.SH", "600238.SH 最近一期经营活动产生的现金流量净额是多少？", "当前现金流量表最近报告期为2025-12-31，经营活动现金流量净额61,500,375.22元。", "financial_cashflow；600238.SH；report_period=20251231；net_cash_flows_oper_act", "high"),
    case("Q4", "跨期比较", "Easy-Medium", "600238.SH", "600238.SH 2025 年与 2024 年相比，营业收入增长了多少？", "母公司口径营业收入由2024年的80,619,370.86元增至2025年的328,367,159.64元，同比增长约307.31%。", "financial_income；600238.SH；report_period=20241231、20251231；oper_rev", "high"),
    case("Q5", "跨期比较", "Easy-Medium", "600238.SH", "600238.SH 过去四个季度的净利润趋势是持续增长、持续下降，还是波动？", "数据不足。当前仅有年度和半年度累计口径，缺少连续四个单季度净利润，不能据此判断四季度趋势。现有最近三期累计值为-68,993,092.03、-4,559,303.87、-8,713,696.22元，呈波动。", "financial_income；600238.SH；report_period=20241231、20250630、20251231；net_profit_excl_min_int_inc；缺少单季度口径", "low"),
    case("Q6", "跨表勾稽", "Medium-Hard", "600238.SH", "600238.SH 最近几个报告期净利润是否持续增长？同期经营活动现金流量净额是否同步增长？如果出现背离，可能的原因是什么？", "净利润并非持续增长：2024年末-68,993,092.03元，2025年中-4,559,303.87元，2025年末-8,713,696.22元。经营现金流同期为-58,467,148.81、18,795,711.96、61,500,375.22元，持续改善。两者口径和趋势不同，但仅凭三表不能断言具体原因，应作为待核实线索。", "financial_income + financial_cashflow；600238.SH；20241231、20250630、20251231", "medium"),
    case("Q7", "跨表勾稽", "Medium-Hard", "600238.SH", "600238.SH 最近两年应收账款和存货的增速，与营业收入增速相比，是否明显偏快？", "2024至2025年，营业收入约增长307.31%，应收账款约增长17.46%，存货约增长3.05%；应收和存货增速均未明显快于收入。仅为母公司口径。", "financial_income + financial_balance；600238.SH；20241231、20251231；oper_rev、acct_rcv、inventories", "high"),
    case("Q8", "跨表勾稽", "Medium-Hard", "600238.SH", "600238.SH 在 2025-12-31 的净利润中，有多大比例来自公允价值变动、投资收益等非主营业务项目？扣除后主营业务是盈利还是亏损？", "该期净利润为-8,713,696.22元，投资净收益为-5,521,034.78元，公允价值变动字段为空；投资项目是损失而非利润来源，其绝对值约为净亏损的63.36%。营业利润为-2,101,418.10元，仍为亏损。不能把空值当作0后做完整扣除。", "financial_income；600238.SH；report_period=20251231；net_profit_excl_min_int_inc、plus_net_invest_inc、plus_net_gain_chg_fv、oper_profit", "medium"),
    case("Q9", "跨表勾稽", "Medium-Hard", "600238.SH", "600238.SH 的短期借款是否明显增加？同时货币资金余额和经营现金流是否在恶化？这是否构成流动性风险信号？", "2024至2025年短期借款约下降14.29%（70,104,805.55降至60,088,000元），货币资金约上升149.96%，经营现金流由-58,467,148.81改善至61,500,375.22元。三项未显示同步恶化，不能据此认定流动性风险；仅为母公司口径。", "financial_balance + financial_cashflow；600238.SH；20241231、20251231；st_borrow、monetary_cap、net_cash_flows_oper_act", "high"),
    case("Q10", "跨表勾稽", "Hard", "600238.SH", "综合 600238.SH 最近三个报告期的利润表、资产负债表、现金流量表，判断是否存在增收不增现迹象，并给出依据和置信度分类。", "最近三期累计口径中，收入和经营现金流总体同时改善，2025年末收入328,367,159.64元、经营现金流61,500,375.22元，未呈现明确增收不增现。净利润仍亏损，属于需继续核实的经营风险；数据为母公司且非连续单季度，结论置信度中等。", "financial_income + financial_balance + financial_cashflow；600238.SH；20241231、20250630、20251231", "medium"),
    case("Q11", "股东穿透", "Medium-Hard", "600238.SH", "600238.SH 的前十大股东中，是否有股东同时出现在另一家公司的前十大股东名单中？如果有，这是否构成需要关注的关联关系？", "有同名交叉：北京燕赵汇金国际投资有限责任公司还出现在000955.SZ、600365.SH，王松涛还出现在000955.SZ、300152.SZ。该结果仅构成待核实线索；同名不能直接证明同一主体或关联关系。", "shareholders；以600238.SH在20260331的股东名反查其他s_info_windcode；s_holder_name", "medium"),
    case("Q12", "股东穿透", "Medium-Hard", "600238.SH", "600238.SH 最近一期相比上一期，前十大股东名单和持股比例是否发生明显变化？", "2026-03-31相比2025-09-30：上海九和寰宇、北京欧德天成退出前十，北京燕赵汇金、王松涛进入；海南联烨持股由1.12%降至0.76%。是否为真实减持仍需结合完整持股变动数据核实。", "shareholders；600238.SH；s_holder_enddate=20250930、20260331；s_holder_name、s_holder_pct", "medium"),
    case("Q13", "公告佐证", "Medium", "600238.SH", "600238.SH 近三年是否被证券监管部门或交易所处罚过？如果有，公告标题和日期是什么？", "有标题级证据：2026-05-01收到海南监管局行政监管措施决定书，2024-06-20被通报批评，2024-06-15收到行政监管措施决定书，另有整改公告。只能确认公告标题所述事件，不能从索引推断处罚细节。", "announcements；600238.SH；ann_dt及n_info_title；2023-08-11至2026-08-11范围内", "high"),
    case("Q14", "公告佐证", "Medium", "600238.SH", "600238.SH 是否存在对外担保类公告？这类担保是否可能构成或有负债风险？", "当前提供的600238.SH风险公告索引中没有标题含“担保”的记录，因此不能确认存在对外担保公告，也不能据此判断或有负债风险。缺失不等于公司一定没有担保。", "announcements；600238.SH；n_info_title LIKE '%担保%'；结果0条", "low"),
    case("Q15", "研报交叉验证", "Medium-Hard", "601033.SH", "601033.SH 的券商研报中对 2025-12-31 净利润的表述，与实际利润表数据是否一致？研报盈利预测属于已确认事实还是分析师观点？", "研报转述2025年合并口径归母净利润8.61亿元；当前financial_income的statement_type=408006000为母公司报表，净利润369,345,561.24元。两者口径不同，不能直接判定一致或矛盾。研报对2026年及以后盈利预测属于分析师观点，不是已确认事实。", "research_reports + financial_income；601033.SH；2025年报研报摘要与report_period=20251231；注意合并/母公司口径", "medium"),
    case("Q16", "研报交叉验证", "Medium-Hard", "601033.SH", "601033.SH 研报提到的风险提示，与实际公告或财务异常信号是否吻合？", "研报包含应收账款回收、政策、垃圾量等风险提示；当前风险公告表对601033.SH为0条，且财务表为母公司口径，无法充分验证这些风险是否已实际发生。应回答数据不足，而非断言吻合。", "research_reports；601033.SH；风险提示文本；announcements匹配0条；财务表口径受限", "low"),
    case("Q17", "边界/拒答", "Boundary", "600238.SH", "600238.SH 被处罚的具体原因和责任人是谁？", "数据不足。公告表只有标题、分类和PDF链接，没有正文；必须解析原公告PDF后才能确认具体原因和责任人。", "announcements；600238.SH；仅n_info_title、n_info_fcode、n_info_annlink，无正文", "low"),
    case("Q18", "边界/拒答", "Boundary", "300838.SZ", "300838.SZ 的实际控制人是谁，控制链条是怎样的？", "数据不足。股东表只有前十大股东快照，不含实际控制人字段及多层控制链，无法回答。", "shareholders字段字典；仅前十大股东及持股关系，无实际控制人/控制链", "low"),
    case("Q19", "边界/拒答", "Boundary", "600238.SH", "600238.SH 的合并报表营业收入是多少？", "数据不足。当前利润表记录的statement_type均为408006000，字段字典定义为母公司报表，不含合并报表，不能回答合并口径营业收入。", "financial_income；600238.SH；statement_type=408006000；income_dict定义为母公司报表", "low"),
]

FIELDNAMES = [
    "question_id",
    "question_content",
    "category",
    "difficulty",
    "涉及公司代码",
    "参考答案",
    "参考数据来源",
    "期望置信度分类",
    "agent_回答",
    "agent_思维链",
    "agent_数据来源引用",
    "agent_置信度分类",
    "是否正确",
    "错误类型",
    "是否幻觉",
    "工具调用步数",
    "token消耗",
    "运行批次",
]


def summarize_trace(trace: list[dict[str, Any]]) -> tuple[str, str, int, str]:
    steps: list[str] = []
    sources: list[str] = []
    tool_steps = 0
    prompt_tokens = completion_tokens = total_tokens = 0
    for event in trace:
        if event.get("event") == "model_response":
            usage = event.get("usage") or {}
            prompt_tokens += int(usage.get("prompt_tokens", 0))
            completion_tokens += int(usage.get("completion_tokens", 0))
            total_tokens += int(usage.get("total_tokens", 0))
            reasoning = event.get("reasoning_content")
            if reasoning:
                steps.append(f"模型 reasoning_content：{reasoning}")
            for call in event.get("tool_calls") or []:
                tool_steps += 1
                function = call.get("function", {})
                name = function.get("name", "unknown")
                try:
                    arguments = json.loads(function.get("arguments", "{}"))
                except json.JSONDecodeError:
                    arguments = function.get("arguments", "")
                steps.append(f"步骤{tool_steps}：调用{name}，参数={json.dumps(arguments, ensure_ascii=False)}")
        elif event.get("event") == "tool_result":
            result = event.get("result")
            steps.append(f"工具返回：{json.dumps(result, ensure_ascii=False, default=str)}")
            if isinstance(result, dict):
                if isinstance(result.get("_source"), str):
                    sources.append(result["_source"])
                for record in result.get("records", []):
                    if isinstance(record, dict) and isinstance(record.get("_source"), str):
                        sources.append(record["_source"])
    token_text = (
        f"prompt_tokens={prompt_tokens}; completion_tokens={completion_tokens}; "
        f"total_tokens={total_tokens}"
    )
    audit_chain = "模型 thinking 已启用；以下记录 API 返回的 reasoning_content 与工具调用轨迹。"
    if steps:
        audit_chain += "\n" + "\n".join(steps)
    return audit_chain, "\n".join(dict.fromkeys(sources)), tool_steps, token_text


def write_outputs(
    csv_path: Path,
    log_path: Path,
    rows: list[dict[str, object]],
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    with log_path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(f"[{row['question_id']}] {row['question_content']}\n")
            file.write(f"类别/难度：{row['category']} / {row['difficulty']}\n")
            file.write(f"参考答案：{row['参考答案']}\n")
            file.write(f"参考数据：{row['参考数据来源']}\n")
            file.write(f"Agent回答：{row['agent_回答']}\n")
            file.write(f"可审计调用轨迹：\n{row['agent_思维链']}\n")
            file.write(f"Agent来源：{row['agent_数据来源引用']}\n")
            file.write(f"Token：{row['token消耗']}\n")
            file.write("-" * 80 + "\n")


def write_artifact(artifacts_dir: Path, question_id: str, question: str,
                   trace: list[dict[str, Any]], answer: dict[str, Any]) -> Path:
    """Persist one structured run without changing annotation CSV semantics."""
    artifacts_dir = Path(artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    artifact = InvestigationRun.from_trace(question, trace, answer, run_id=question_id)
    path = artifacts_dir / f"{question_id}.json"
    path.write_text(artifact.to_json() + "\n", encoding="utf-8")
    return path


def run(csv_path: Path, log_path: Path, batch: str, artifacts_dir: Path | None = None) -> None:
    rows: list[dict[str, object]] = []
    for index, test_case in enumerate(CASES, 1):
        print(f"[{index:02d}/{len(CASES)}] {test_case['question_id']} {test_case['question_content']}", flush=True)
        trace: list[dict[str, Any]] = []
        started = time.perf_counter()
        try:
            answer = run_agent(test_case["question_content"], trace=trace)
            error_type = ""
        except Exception as exc:
            answer = {"结论": f"运行失败：{type(exc).__name__}: {exc}", "证据": [], "置信度": ""}
            error_type = "运行错误"
        elapsed = time.perf_counter() - started
        chain, actual_sources, tool_steps, tokens = summarize_trace(trace)
        agent_answer = answer.get("结论", "")
        evidence = answer.get("证据", [])
        if evidence:
            agent_answer += "\n证据：" + json.dumps(evidence, ensure_ascii=False)
        agent_answer += f"\n运行耗时：{elapsed:.3f}秒"
        row: dict[str, object] = dict(test_case)
        row.update(
            {
                "agent_回答": agent_answer,
                "agent_思维链": chain or "未产生工具调用轨迹",
                "agent_数据来源引用": actual_sources or json.dumps(evidence, ensure_ascii=False),
                "agent_置信度分类": answer.get("置信度", ""),
                "是否正确": "",
                "错误类型": error_type,
                "是否幻觉": "",
                "工具调用步数": tool_steps,
                "token消耗": tokens,
                "运行批次": batch,
            }
        )
        rows.append(row)
        write_outputs(csv_path, log_path, rows)
        if artifacts_dir is not None:
            write_artifact(artifacts_dir, test_case["question_id"], test_case["question_content"], trace, answer)
    print(f"Wrote {len(rows)} rows to {csv_path}")
    print(f"Wrote readable log to {log_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "results" / "agent_error_analysis.csv",
    )
    parser.add_argument("--log", type=Path)
    parser.add_argument("--batch")
    parser.add_argument("--artifacts-dir", type=Path,
                        help="optional directory for one InvestigationRun JSON per case")
    args = parser.parse_args()
    batch = args.batch or datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = args.log or args.output.with_suffix(".log")
    run(args.output, log_path, batch, args.artifacts_dir)


if __name__ == "__main__":
    main()
