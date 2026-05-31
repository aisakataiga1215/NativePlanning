"""CLI entry point for NativePlanning.

Usage:
    python -m src.cli.main family
    python -m src.cli.main friends
    python -m src.cli.main failure-no-seats
    python -m src.cli.main failure-no-tickets
    python -m src.cli.main failure-time-conflict
    python -m src.cli.main "今天下午想带孩子去公园玩"
"""
from __future__ import annotations

import io
import sys

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

load_dotenv()

from src.tools.wrappers import TraceLog
from src.workflow.intent_parser import parse_intent, parse_free_text
from src.workflow.planner import generate_candidate_plans
from src.workflow.constraint_solver import validate_and_repair
from src.workflow.executor import execute_plan
from src.workflow.message_agent import generate_share_message
from src.services.plan_ranker import rank_plans

console = Console(file=io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8"), legacy_windows=False)

_KNOWN_SCENARIOS = [
    "family",
    "friends",
    "failure-no-seats",
    "failure-no-tickets",
    "failure-time-conflict",
]

_FAILURE_FLAGS = {
    "failure-no-seats": {"force_no_seats": True},
    "failure-no-tickets": {"force_no_tickets": True},
    "failure-time-conflict": {"force_time_conflict": True},
}


def run(scenario_key: str) -> None:
    log = TraceLog()

    # ── 1. Intent ────────────────────────────────────────────────────────────
    intent = parse_intent(scenario_key)
    _print_intent(intent)

    # ── 2. Generate candidate plans ─────────────────────────────────────────
    plans = generate_candidate_plans(intent, log)
    if not plans:
        console.print("[bold red]未找到合适的计划，请调整条件后重试。[/]")
        return

    # ── 3. Validate & repair (inject failure flags if needed) ────────────────
    flags = _FAILURE_FLAGS.get(scenario_key, {})
    repaired = [validate_and_repair(p, intent, log, **flags) for p in plans]

    # ── 4. Rank ──────────────────────────────────────────────────────────────
    ranked = rank_plans(repaired, intent.max_distance_km, intent.duration_hours)
    best = ranked[0]

    # ── 5. Print tool trace ──────────────────────────────────────────────────
    _print_trace(log)

    # ── 6. Print plan ────────────────────────────────────────────────────────
    _print_plan(best)

    # ── 7. Execute ───────────────────────────────────────────────────────────
    results = execute_plan(best, intent, log)
    _print_execution(results)

    # ── 8. Share message ─────────────────────────────────────────────────────
    msg = generate_share_message(best, results, intent)
    console.print(Panel(
        f"[bold cyan]{msg.message}[/]",
        title="[bold green]📱 分享消息[/]",
        border_style="green",
    ))


def run_free_text(user_input: str) -> None:
    """Run the full pipeline from free-form natural language input."""
    import os
    log = TraceLog()

    # ── 1. Parse intent (LLM or rule-based fallback) ─────────────────────────
    intent = parse_free_text(user_input)
    has_key = bool(os.getenv("OPENAI_API_KEY"))
    source = "[LLM]" if has_key else "[rule-based]"
    _print_intent(intent, source=source)

    # ── 2-8: Same pipeline as run() ──────────────────────────────────────────
    plans = generate_candidate_plans(intent, log)
    if not plans:
        console.print("[bold red]未找到合适的计划，请调整条件后重试。[/]")
        return

    repaired = [validate_and_repair(p, intent, log) for p in plans]
    ranked = rank_plans(repaired, intent.max_distance_km, intent.duration_hours)
    best = ranked[0]

    _print_trace(log)
    _print_plan(best)

    results = execute_plan(best, intent, log)
    _print_execution(results)

    msg = generate_share_message(best, results, intent)
    console.print(Panel(
        f"[bold cyan]{msg.message}[/]",
        title="[bold green]📱 分享消息[/]",
        border_style="green",
    ))


def _print_intent(intent, source: str | None = None) -> None:
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("场景", intent.scenario_type)
    t.add_row("人数", str(intent.group_size))
    t.add_row("出发时间", f"{intent.date} {intent.time}")
    t.add_row("时长", f"{intent.duration_hours} 小时")
    t.add_row("最远距离", f"{intent.max_distance_km} km")
    if intent.raw_input:
        t.add_row("原始输入", intent.raw_input)
    title = "[bold]1. 意图解析[/]"
    if source:
        title += f"  [dim]{source}[/]"
    console.print(Panel(t, title=title, border_style="blue"))


def _print_trace(log: TraceLog) -> None:
    t = Table(box=box.SIMPLE, padding=(0, 1))
    t.add_column("工具", style="cyan", no_wrap=True)
    t.add_column("状态", no_wrap=True)
    t.add_column("结果摘要")
    t.add_column("耗时(ms)", justify="right", style="dim")

    for tr in log.traces:
        status_str = "[green]✓[/]" if tr.status == "ok" else "[red]✗[/]"
        if tr.status == "ok" and isinstance(tr.output, list):
            summary = f"{len(tr.output)} 项"
        elif tr.status == "ok" and isinstance(tr.output, dict):
            summary = str(tr.output.get("available", tr.output))[:60]
        elif tr.status == "ok" and hasattr(tr.output, "status"):
            summary = f"{tr.output.status}: {tr.output.message[:50]}"
        elif tr.status == "error":
            summary = f"[red]{tr.error}[/]"
        else:
            summary = str(tr.output)[:60]
        t.add_row(tr.tool_name, status_str, summary, f"{tr.elapsed_ms}")

    console.print(Panel(t, title="[bold]2. 工具调用追踪[/]", border_style="yellow"))


def _print_plan(plan) -> None:
    if plan.warnings:
        for w in plan.warnings:
            console.print(f"  [bold yellow]{w}[/]")

    t = Table(box=box.SIMPLE_HEAD, padding=(0, 1))
    t.add_column("时间", style="cyan", no_wrap=True)
    t.add_column("步骤")
    t.add_column("地点")
    t.add_column("时长", justify="right")
    for s in plan.steps:
        t.add_row(
            f"{s.start_time}–{s.end_time}",
            s.title,
            s.location_name,
            f"{s.duration_minutes}min",
        )

    sb = plan.score_breakdown
    score_str = (
        f"综合评分: [bold]{plan.score:.2f}[/]  "
        f"距离:{sb.distance_score:.2f}  时间:{sb.time_score:.2f}  "
        f"适配:{sb.group_fit_score:.2f}  餐厅:{sb.restaurant_score:.2f}  "
        f"可执行:{sb.execution_score:.2f}"
    )
    reasons_str = "\n".join(f"  ✓ {r}" for r in plan.reasons)
    risks_str = "\n".join(f"  ⚠ {r}" for r in plan.risks) if plan.risks else "  （无风险）"
    cost_str = f"预估费用: ¥{plan.estimated_total_cost:.0f}"

    body = f"{score_str}\n\n{reasons_str}\n\n风险:\n{risks_str}\n\n{cost_str}"
    console.print(Panel(t, title="[bold]3. 推荐计划 – " + plan.title + "[/]", border_style="magenta"))
    console.print(Panel(body, title="[bold]评分与理由[/]", border_style="magenta"))


def _print_execution(results) -> None:
    if not results:
        console.print(Panel("（无需执行操作）", title="[bold]4. 执行结果[/]", border_style="green"))
        return
    t = Table(box=box.SIMPLE, padding=(0, 1))
    t.add_column("操作", style="cyan")
    t.add_column("状态")
    t.add_column("详情")
    for r in results:
        status_str = "[green]✓ 成功[/]" if r.status == "success" else "[red]✗ 失败[/]"
        ref = r.booking_id or r.order_id or ""
        detail = f"{r.message}  [dim]{ref}[/]" if ref else r.message
        t.add_row(r.action_type, status_str, detail)
    console.print(Panel(t, title="[bold]4. 执行结果[/]", border_style="green"))


def main() -> None:
    if len(sys.argv) < 2:
        console.print("[bold red]用法:[/] python -m src.cli.main <scenario|自然语言输入>")
        console.print(f"内置场景: {', '.join(_KNOWN_SCENARIOS)}")
        console.print('自由输入: python -m src.cli.main "今天下午带孩子去公园"')
        sys.exit(1)

    arg = " ".join(sys.argv[1:])
    if arg in _KNOWN_SCENARIOS:
        run(arg)
    else:
        run_free_text(arg)


if __name__ == "__main__":
    main()
