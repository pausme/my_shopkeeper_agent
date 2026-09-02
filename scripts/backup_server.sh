#!/bin/bash
# 服务器数据备份：MySQL 逻辑导出 + Qdrant / ES 数据卷打包，保留最近 N 天
# 建议由 crontab 每日调用，例如：
#   17 4 * * * /home/ubuntu/shopkeeper-agent/scripts/backup_server.sh >> /home/ubuntu/backups/backup.log 2>&1
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$HOME/shopkeeper-agent}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups}"
KEEP_DAYS="${KEEP_DAYS:-7}"

mkdir -p "$BACKUP_DIR"
STAMP=$(date +%Y%m%d_%H%M%S)

# 从应用 .env 读取数据库口令（mysqldump 在容器内执行，走 localhost）
DB_PASSWORD=$(grep '^DB_PASSWORD=' "$PROJECT_DIR/.env" | cut -d= -f2 | tr -d '\r')

echo "[$(date '+%F %T')] backup start"

# 1. MySQL：meta 与 dw 库逻辑导出（gzip 压缩）
docker exec mysql mysqldump -uroot -p"$DB_PASSWORD" --databases meta dw \
  | gzip > "$BACKUP_DIR/mysql_$STAMP.sql.gz"

# 2. Qdrant / ES：用一次性 alpine 容器打包数据卷
docker run --rm \
  -v docker_qdrant_data:/data:ro \
  -v "$BACKUP_DIR":/backup \
  alpine tar czf "/backup/qdrant_$STAMP.tar.gz" -C /data .

docker run --rm \
  -v docker_es_data:/data:ro \
  -v "$BACKUP_DIR":/backup \
  alpine tar czf "/backup/es_$STAMP.tar.gz" -C /data .

# 3. 清理过期备份
find "$BACKUP_DIR" -name "*.gz" -type f -mtime "+$KEEP_DAYS" -delete

echo "[$(date '+%F %T')] backup done: $(du -sh "$BACKUP_DIR" | cut -f1) total, latest:"
ls -1t "$BACKUP_DIR"/*.gz | head -3
