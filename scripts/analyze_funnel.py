"""
UI 改版效果评估（N10.5）

从埋点与反馈表计算改版核心指标，供改版前后对比：
- 推荐点击率 = product_click / recommendation_shown
- 追问率     = 有追问的会话数 / 有推荐的会话数（推荐产生后的后续 query_start）
- 有帮助反馈率 = helpful / 全部反馈

用法（服务器或可连 meta 库的环境）：
  .venv/bin/python scripts/analyze_funnel.py [天数，默认 14]
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from sqlalchemy import func, select

from app.clients.mysql_client_manager import meta_mysql_client_manager
from app.models.shopping import ShoppingEventLogMySQL, ShoppingFeedbackMySQL


async def main() -> int:
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 14
    since = datetime.now() - timedelta(days=days)

    meta_mysql_client_manager.init()
    async with meta_mysql_client_manager.session_factory() as session:
        def count(event_type: str):
            return (
                select(func.count())
                .select_from(ShoppingEventLogMySQL)
                .where(
                    ShoppingEventLogMySQL.event_type == event_type,
                    ShoppingEventLogMySQL.created_at >= since,
                )
                .scalar_subquery()
            )

        shown = (await session.execute(count("recommendation_shown"))).scalar() or 0
        clicks = (await session.execute(count("product_click"))).scalar() or 0

        # 追问：会话内在首个 query_start 之后再次出现 query_start
        query_sessions = (
            await session.execute(
                select(ShoppingEventLogMySQL.session_id, func.count())
                .where(
                    ShoppingEventLogMySQL.event_type == "query_start",
                    ShoppingEventLogMySQL.created_at >= since,
                )
                .group_by(ShoppingEventLogMySQL.session_id)
            )
        ).all()
        sessions_with_query = len(query_sessions)
        sessions_with_followup = sum(1 for _, n in query_sessions if n > 1)

        feedback_rows = (
            await session.execute(
                select(ShoppingFeedbackMySQL.feedback_type, func.count())
                .where(ShoppingFeedbackMySQL.created_at >= since)
                .group_by(ShoppingFeedbackMySQL.feedback_type)
            )
        ).all()
        feedback_total = sum(n for _, n in feedback_rows)
        feedback_helpful = dict(feedback_rows).get("helpful", 0)

    def rate(numerator: int, denominator: int) -> str:
        return f"{numerator / denominator:.1%}" if denominator else "n/a（样本为 0）"

    print(f"UI 改版指标（近 {days} 天，截至 {datetime.now():%Y-%m-%d %H:%M}）")
    print(f"  推荐点击率      {clicks}/{shown} = {rate(clicks, shown)}")
    print(
        f"  追问率          {sessions_with_followup}/{sessions_with_query} = "
        f"{rate(sessions_with_followup, sessions_with_query)}"
    )
    print(f"  有帮助反馈率    {feedback_helpful}/{feedback_total} = {rate(feedback_helpful, feedback_total)}")
    print("  反馈分布：", ", ".join(f"{t}={n}" for t, n in feedback_rows) or "无")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
