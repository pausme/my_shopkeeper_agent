"""
关注与降价提醒仓储（二期 S2）
"""

from sqlalchemy import desc, select

from app.models.shopping import (
    ShoppingPriceAlertMySQL,
    ShoppingWatchlistMySQL,
)
from app.repositories.mysql.meta.shopping_repositories import new_id


class WatchlistRepository:
    """商品关注与价格提醒的持久化"""

    def __init__(self, session):
        self.session = session

    async def watch(
        self,
        user_id: str,
        product_id: str,
        product_title: str | None,
        target_price: float | None,
        current_price: float | None,
    ) -> tuple[ShoppingWatchlistMySQL, bool]:
        """关注商品（幂等：同用户同商品重复关注返回已有记录）；返回 (行, 是否新建)"""

        result = await self.session.execute(
            select(ShoppingWatchlistMySQL).where(
                ShoppingWatchlistMySQL.user_id == user_id,
                ShoppingWatchlistMySQL.product_id == product_id,
                ShoppingWatchlistMySQL.status != "canceled",
            )
        )
        row = result.scalars().first()
        if row is not None:
            # 已关注：允许更新目标价
            if target_price is not None:
                row.target_price = target_price
            return row, False

        row = ShoppingWatchlistMySQL(
            watch_id=new_id("W"),
            user_id=user_id,
            product_id=product_id,
            product_title_snapshot=(product_title or "")[:255],
            target_price=target_price,
            current_price=current_price,
            status="active",
        )
        self.session.add(row)
        return row, True

    async def unwatch(self, user_id: str, product_id: str) -> bool:
        """取消关注（幂等）"""

        result = await self.session.execute(
            select(ShoppingWatchlistMySQL).where(
                ShoppingWatchlistMySQL.user_id == user_id,
                ShoppingWatchlistMySQL.product_id == product_id,
                ShoppingWatchlistMySQL.status != "canceled",
            )
        )
        row = result.scalars().first()
        if row is None:
            return False
        row.status = "canceled"
        return True

    async def list_by_user(self, user_id: str) -> list[dict]:
        """用户全部有效关注"""

        result = await self.session.execute(
            select(ShoppingWatchlistMySQL)
            .where(
                ShoppingWatchlistMySQL.user_id == user_id,
                ShoppingWatchlistMySQL.status != "canceled",
            )
            .order_by(desc(ShoppingWatchlistMySQL.created_at))
        )
        return [
            {
                "watch_id": row.watch_id,
                "product_id": row.product_id,
                "product_title": row.product_title_snapshot,
                "target_price": float(row.target_price) if row.target_price else None,
                "current_price": float(row.current_price) if row.current_price else None,
                "status": row.status,
                "created_at": int(row.created_at.timestamp() * 1000)
                if row.created_at
                else None,
            }
            for row in result.scalars()
        ]

    async def get_watch(self, watch_id: str, user_id: str) -> ShoppingWatchlistMySQL | None:
        """按 watch_id 查属主关注行"""

        result = await self.session.execute(
            select(ShoppingWatchlistMySQL).where(
                ShoppingWatchlistMySQL.watch_id == watch_id,
                ShoppingWatchlistMySQL.user_id == user_id,
                ShoppingWatchlistMySQL.status != "canceled",
            )
        )
        return result.scalars().first()

    async def save_alert(
        self,
        watch_id: str,
        user_id: str,
        product_id: str,
        alert_price: float,
        alert_reason: str,
    ) -> str:
        """记录一条命中的降价提醒"""

        alert_id = new_id("A")
        self.session.add(
            ShoppingPriceAlertMySQL(
                alert_id=alert_id,
                watch_id=watch_id,
                user_id=user_id,
                product_id=product_id,
                alert_price=alert_price,
                alert_reason=alert_reason[:500],
            )
        )
        return alert_id

    async def list_alerts(self, user_id: str, limit: int = 20) -> list[dict]:
        """用户最近提醒（含未读）"""

        result = await self.session.execute(
            select(ShoppingPriceAlertMySQL)
            .where(ShoppingPriceAlertMySQL.user_id == user_id)
            .order_by(desc(ShoppingPriceAlertMySQL.created_at))
            .limit(limit)
        )
        return [
            {
                "alert_id": row.alert_id,
                "watch_id": row.watch_id,
                "product_id": row.product_id,
                "alert_price": float(row.alert_price),
                "alert_reason": row.alert_reason,
                "alert_status": row.alert_status,
                "created_at": int(row.created_at.timestamp() * 1000)
                if row.created_at
                else None,
            }
            for row in result.scalars()
        ]
