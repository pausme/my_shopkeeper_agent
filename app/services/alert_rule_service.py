"""
提醒规则配置（二期 P2）

规则存 shopping_alert_rule 表（rule_key 唯一），check_price_alerts 脚本
读取规则决定是否为某用户生成提醒。默认规则内置。
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert_rule import AlertRuleMySQL

# 内置默认规则（数据库无配置时的兜底）
DEFAULT_RULES: list[dict] = [
    {
        "rule_key": "global",
        "description": "全局开关与默认限频",
        "value_json": {"enabled": True, "max_per_day": 3},
    },
    {
        "rule_key": "quiet_hours",
        "description": "静默时段（此区间不生成新提醒，时段结束后下一轮检查补上）",
        "value_json": {"start": "22:00", "end": "08:00"},
    },
]


class AlertRuleService:
    """提醒规则的读写（管理台与价格检查脚本共用）"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_rules(self) -> list[dict]:
        """全部规则；空表时返回内置默认（不写库）"""

        result = await self.session.execute(select(AlertRuleMySQL))
        rows = list(result.scalars())
        if not rows:
            return [
                {"rule_key": r["rule_key"], "description": r["description"], **r["value_json"]}
                for r in DEFAULT_RULES
            ]
        return [
            {
                "rule_key": row.rule_key,
                "description": row.description,
                **(row.value_json or {}),
            }
            for row in rows
        ]

    async def upsert_rule(
        self, rule_key: str, description: str | None, value_json: dict
    ) -> None:
        """新增或更新规则"""

        result = await self.session.execute(
            select(AlertRuleMySQL).where(AlertRuleMySQL.rule_key == rule_key)
        )
        row = result.scalars().first()
        if row is None:
            self.session.add(
                AlertRuleMySQL(
                    rule_key=rule_key,
                    description=description,
                    value_json=value_json,
                )
            )
        else:
            if description is not None:
                row.description = description
            row.value_json = value_json

    async def get_effective(self) -> dict:
        """合并后的生效规则（内置默认 + 数据库覆盖）"""

        result = await self.session.execute(select(AlertRuleMySQL))
        overrides = {row.rule_key: row.value_json or {} for row in result.scalars()}
        effective: dict = {"enabled": True, "max_per_day": 3, "quiet_hours": None}
        for rule in DEFAULT_RULES:
            override = overrides.get(rule["rule_key"])
            merged = {**rule["value_json"], **(override or {})}
            effective[rule["rule_key"]] = merged
        for key, override in overrides.items():
            if key not in effective:
                effective[key] = override
        return effective
