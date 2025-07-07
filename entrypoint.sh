#!/bin/bash
# 應用程式啟動腳本 - 包含資料庫遷移

set -e

echo "Starting Gemini Balance..."

# 檢查並執行資料庫遷移
if [ -f "/app/migrations/migration_manager.py" ]; then
    echo "Checking database migrations..."
    python /app/migrations/migration_manager.py --quiet || {
        echo "Running database migrations..."
        python /app/migrations/migration_manager.py
    }
else
    echo "No migration manager found, skipping migrations"
fi

# 啟動應用程式
echo "Starting application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log