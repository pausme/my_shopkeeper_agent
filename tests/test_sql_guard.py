"""
sql_guard 只读校验器单元测试

覆盖：合法 SELECT、CTE、UNION，以及各类应被拒绝的语句。
"""

from app.agent.sql_guard import validate_readonly


def test_plain_select_passes():
    assert validate_readonly("SELECT sum(order_amount) FROM dw.fact_order") is None


def test_select_with_trailing_semicolon_passes():
    assert validate_readonly("SELECT 1 AS x;") is None


def test_cte_select_passes():
    assert validate_readonly("WITH t AS (SELECT 1 AS x) SELECT x FROM t") is None


def test_union_select_passes():
    sql = "SELECT region_name FROM dim_region UNION ALL SELECT province FROM dim_region"
    assert validate_readonly(sql) is None


def test_update_rejected():
    error = validate_readonly("UPDATE fact_order SET order_amount = 0")
    assert error is not None and "SELECT" in error


def test_delete_rejected():
    assert validate_readonly("DELETE FROM fact_order") is not None


def test_drop_rejected():
    assert validate_readonly("DROP TABLE fact_order") is not None


def test_insert_rejected():
    assert validate_readonly("INSERT INTO dim_region VALUES ('R9', 'x', 'y', 'z')") is not None


def test_multiple_statements_rejected():
    error = validate_readonly("SELECT 1; SELECT 2")
    assert error is not None and "单条" in error


def test_garbage_rejected():
    assert validate_readonly("这不是SQL") is not None


def test_empty_rejected():
    assert validate_readonly("") is not None
    assert validate_readonly("   ") is not None
