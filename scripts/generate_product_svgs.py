"""
商品主图 SVG 生成器（N11.10，独立运行，无需数据库/检索服务）

为每款商品生成专属 SVG 主图并写入 frontend/public/products/，
随仓库提交后由 Vite 构建自动打包进 dist。用法：
    LLM_API_KEY=dummy uv run python scripts/generate_product_svgs.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
os.environ.setdefault("LLM_API_KEY", "dummy")

from scripts.seed_shopping_data import build_products  # noqa: E402


def main() -> None:
    products = build_products()
    print(f"生成 {len(products)} 款商品主图（build_products 内含写盘）")


if __name__ == "__main__":
    main()
