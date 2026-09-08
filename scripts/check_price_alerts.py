"""
价格检查定时任务（二期 S2-4）

扫描全部 active 关注记录，对照商品当前价（promotion_price 优先）：
命中目标价时生成 shopping_price_alert 记录并把关注状态置为 triggered。
由服务器 crontab 定时执行（演示数据下每次运行都会对比，重复命中由 alert
记录天然去重——关注状态已 triggered 不再重复生成，除非用户重新设置目标价）。

用法：API_TOKEN 不需要。crontab 示例（每小时的 17 分）：
  17 * * * * cd /home/ubuntu/shopkeeper-agent && .venv/bin/python scripts/check_price_alerts.py >> logs/price_alerts.log 2>&1
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from datetime import datetime

from sqlalchemy import select

from app.clients.mysql_client_manager import meta_mysql_client_manager
from app.models.product import ProductInfoMySQL
from app.models.shopping import ShoppingWatchlistMySQL
from app.repositories.mysql.meta.watchlist_repository import WatchlistRepository
from app.services.alert_rule_service import AlertRuleService


def _in_quiet_hours(now: datetime, quiet: dict) -> bool:
    """当前时刻是否落在静默时段（支持 22:00-08:00 跨午夜窗口）"""

    try:
        start = datetime.strptime(str(quiet.get("start", "22:00")), "%H:%M").time()
        end = datetime.strptime(str(quiet.get("end", "08:00")), "%H:%M").time()
    except ValueError:
        return False
    current = now.time()
    if start <= end:
        return start <= current < end
    return current >= start or current < end


async def main() -> int:
    meta_mysql_client_manager.init()
    created = 0
    checked = 0

    async with meta_mysql_client_manager.session_factory() as session:
        result = await session.execute(
            select(ShoppingWatchlistMySQL).where(
                ShoppingWatchlistMySQL.status == "active"
            )
        )
        watches = list(result.scalars())

        repository = WatchlistRepository(session)

        # P2 规则：全局开关关闭时整轮跳过（不打扰用户）
        effective = await AlertRuleService(session).get_effective()
        global_rule = effective.get("global", {})
        if not global_rule.get("enabled", True):
            print("提醒全局开关已关闭，跳过本轮生成")
            print("PRICE_CHECK_DONE: checked=0 alerts_created=0")
            return 0

        # P2 规则：静默时段内不生成新提醒，时段结束后下一轮补上
        quiet_rule = effective.get("quiet_hours") or {}
        if _in_quiet_hours(datetime.now(), quiet_rule):
            print(
                "当前处于静默时段"
                f"（{quiet_rule.get('start', '22:00')}-{quiet_rule.get('end', '08:00')}），跳过本轮生成"
            )
            print("PRICE_CHECK_DONE: checked=0 alerts_created=0")
            return 0

        for watch in watches:
            # 读商品当前价
            product_result = await session.execute(
                select(ProductInfoMySQL).where(
                    ProductInfoMySQL.product_id == watch.product_id,
                    ProductInfoMySQL.is_deleted == 0,
                )
            )
            product = product_result.scalars().first()
            if product is None:
                continue
            checked += 1

            current = float(product.promotion_price or product.price)
            watch.current_price = current

            # 命中条件：当前价 <= 目标价（未设目标价不触发）
            if watch.target_price is None or current > float(watch.target_price):
                continue
            if watch.status == "triggered":
                continue  # 已触发过，等用户重新调整目标价

            # P2 规则：单用户每日上限
            recent = await repository.list_alerts(watch.user_id, limit=50)
            today_str = datetime.now().strftime("%Y-%m-%d")
            sent_today = sum(
                1
                for a in recent
                if a.get("created_at")
                and datetime.fromtimestamp(a["created_at"] / 1000).strftime("%Y-%m-%d")
                == today_str
            )
            if sent_today >= int(global_rule.get("max_per_day", 3)):
                print(f"用户 {watch.user_id} 今日提醒已达上限，跳过")
                continue

            reason = (
                f"商品「{product.title}」当前到手价 {current} 元，"
                f"已达到你设置的目标价 {watch.target_price} 元"
            )
            await repository.save_alert(
                watch_id=watch.watch_id,
                user_id=watch.user_id,
                product_id=watch.product_id,
                alert_price=current,
                alert_reason=reason,
            )
            watch.status = "triggered"
            created += 1
            print(f"ALERT created: user={watch.user_id} product={watch.product_id} price={current}")

        await session.commit()

    print(f"PRICE_CHECK_DONE: checked={checked} alerts_created={created}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
