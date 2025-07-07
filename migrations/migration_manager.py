#!/usr/bin/env python3
"""
資料庫遷移管理器
支援多個版本的遷移腳本
"""
import sqlite3
import os
import sys
from datetime import datetime
from typing import List, Tuple

# 資料庫路徑 - 使用環境變數或預設值
DB_NAME = os.environ.get('SQLITE_DATABASE', 'default_db')
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', DB_NAME)

# 所有遷移定義（版本號，描述，遷移函數）
MIGRATIONS = []

def register_migration(version: int, description: str):
    """裝飾器：註冊遷移函數"""
    def decorator(func):
        MIGRATIONS.append((version, description, func))
        return func
    return decorator

def create_migration_table(conn):
    """創建遷移歷史表"""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS t_migration_history (
            version INTEGER PRIMARY KEY,
            description TEXT,
            applied_at TIMESTAMP,
            status TEXT
        )
    """)
    conn.commit()

def get_applied_migrations(conn) -> List[int]:
    """獲取已應用的遷移版本"""
    cursor = conn.cursor()
    cursor.execute("SELECT version FROM t_migration_history WHERE status = 'success'")
    return [row[0] for row in cursor.fetchall()]

def record_migration(conn, version: int, description: str, status: str):
    """記錄遷移執行狀態"""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO t_migration_history (version, description, applied_at, status)
        VALUES (?, ?, ?, ?)
    """, (version, description, datetime.now(), status))
    conn.commit()

# ========== 遷移定義 ==========

@register_migration(1, "添加請求日誌詳細欄位")
def migration_v1_add_request_log_details(conn):
    """第一版遷移：添加請求日誌詳細欄位"""
    cursor = conn.cursor()
    
    # 檢查表是否存在
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='t_request_log'
    """)
    if not cursor.fetchone():
        raise Exception("表 t_request_log 不存在")
    
    # 要添加的欄位
    columns_to_add = [
        ("request_body", "TEXT"),
        ("response_summary", "TEXT"),
        ("prompt_tokens", "INTEGER"),
        ("completion_tokens", "INTEGER"),
        ("total_tokens", "INTEGER"),
        ("error_message", "TEXT")
    ]
    
    # 檢查並添加欄位
    added = 0
    for column_name, column_type in columns_to_add:
        cursor.execute(f"PRAGMA table_info(t_request_log)")
        columns = [row[1] for row in cursor.fetchall()]
        if column_name not in columns:
            cursor.execute(f"ALTER TABLE t_request_log ADD COLUMN {column_name} {column_type} NULL")
            added += 1
            print(f"  ✅ 已添加欄位: {column_name}")
        else:
            print(f"  ⏭️  欄位已存在: {column_name}")
    
    if added > 0:
        print(f"  已添加 {added} 個新欄位")

@register_migration(2, "示例：添加新功能表")
def migration_v2_example(conn):
    """第二版遷移示例：創建新表或修改現有表"""
    # 這是一個示例，實際使用時替換為真實的遷移邏輯
    cursor = conn.cursor()
    
    # 示例：創建新表
    # cursor.execute("""
    #     CREATE TABLE IF NOT EXISTS t_new_feature (
    #         id INTEGER PRIMARY KEY AUTOINCREMENT,
    #         name TEXT NOT NULL,
    #         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    #     )
    # """)
    
    # 示例：修改現有表
    # cursor.execute("ALTER TABLE t_existing_table ADD COLUMN new_column TEXT")
    
    print("  ⏭️  示例遷移（跳過）")

# ========== 主程序 ==========

def run_migrations(quiet_mode=False):
    """執行所有待處理的遷移"""
    if not os.path.exists(DB_PATH):
        if not quiet_mode:
            print(f"❌ 資料庫不存在: {DB_PATH}")
        return False
    
    try:
        # 連接資料庫
        conn = sqlite3.connect(DB_PATH)
        
        # 創建遷移歷史表
        create_migration_table(conn)
        
        # 獲取已應用的遷移
        applied_versions = get_applied_migrations(conn)
        
        # 排序遷移（按版本號）
        MIGRATIONS.sort(key=lambda x: x[0])
        
        # 執行待處理的遷移
        pending_migrations = [m for m in MIGRATIONS if m[0] not in applied_versions]
        
        if not pending_migrations:
            if not quiet_mode:
                print("✅ 所有遷移都已應用，無需執行")
            return True
        
        if not quiet_mode:
            print(f"發現 {len(pending_migrations)} 個待處理的遷移")
        
        for version, description, migration_func in pending_migrations:
            if not quiet_mode:
                print(f"\n🔄 執行遷移 v{version}: {description}")
            
            try:
                migration_func(conn)
                record_migration(conn, version, description, "success")
                if not quiet_mode:
                    print(f"✅ 遷移 v{version} 成功完成")
            except Exception as e:
                record_migration(conn, version, description, f"failed: {str(e)}")
                if not quiet_mode:
                    print(f"❌ 遷移 v{version} 失敗: {e}")
                conn.rollback()
                raise
        
        conn.close()
        return True
        
    except Exception as e:
        if not quiet_mode:
            print(f"❌ 遷移執行失敗: {e}")
        return False

def main():
    """主函數"""
    quiet_mode = '--quiet' in sys.argv
    
    if not quiet_mode:
        print("=" * 50)
        print("Gemini Balance - 資料庫遷移管理器")
        print("=" * 50)
        print(f"資料庫路徑: {DB_PATH}")
        print(f"執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)
    
    success = run_migrations(quiet_mode)
    
    if not quiet_mode:
        print("=" * 50)
        if success:
            print("🎉 所有遷移執行完成！")
        else:
            print("😞 遷移執行失敗")
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()