"""
SQL 只读校验器

在 SQL 真正执行前用 sqlglot 做语法层面的硬校验：
仅允许单条 SELECT（含 UNION / 带 CTE 的 SELECT）语句，拒绝一切写入和 DDL。
这是对提示词约束的程序化兜底，防止模型生成或"修正"出非查询语句。
"""

import sqlglot
from sqlglot import expressions as exp

# 允许执行的语句类型：普通查询、UNION 查询（CTE 会挂在 Select 的 with 属性上）
_ALLOWED_ROOT_TYPES = (exp.Select, exp.Union)


def validate_readonly(sql: str) -> str | None:
    """校验 SQL 是否为单条只读查询

    返回 None 表示通过；返回错误描述字符串表示不通过。
    """

    if not sql or not sql.strip():
        return "SQL 为空"

    try:
        # 按 MySQL 方言解析；sqlglot 能容忍结尾分号
        statements = sqlglot.parse(sql, read="mysql")
    except sqlglot.errors.ParseError as e:
        return f"SQL 解析失败：{e}"

    statements = [stmt for stmt in statements if stmt is not None]
    if len(statements) != 1:
        return f"仅允许单条 SQL 语句，当前解析出 {len(statements)} 条"

    stmt = statements[0]
    if not isinstance(stmt, _ALLOWED_ROOT_TYPES):
        return f"仅允许 SELECT 查询语句，当前语句类型为 {type(stmt).__name__}"

    return None
