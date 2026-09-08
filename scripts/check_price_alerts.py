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

from sqlalchemy import select

from app.clients.mysql_client_manager import meta_mysql_client_manager
from app.models.product import ProductInfoMySQL
from app.models.shopping import ShoppingWatchlistMySQL
from app.repositories.mysql.meta.watchlist_repository import WatchlistRepository


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
        for watch in watches:
            # 读商品当前价
            from sqlalchemy import select as s

            product_result = await session.execute(
                s(ProductInfoMySQL).where(
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
