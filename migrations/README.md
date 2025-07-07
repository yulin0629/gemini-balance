# 資料庫遷移指南

本項目使用自動化的資料庫遷移系統，支援 SQLite 資料庫的版本控制和升級。

## 遷移系統特點

1. **自動執行**：在 `dev-deploy.sh` 的各種模式下自動檢查並執行遷移
2. **版本控制**：每個遷移都有唯一的版本號，系統會追蹤已執行的遷移
3. **智能檢測**：只執行尚未應用的遷移，避免重複執行
4. **錯誤處理**：遷移失敗時會回滾並記錄錯誤

## 如何添加新的資料庫遷移

### 1. 編輯 `migration_manager.py`

在文件中添加新的遷移函數：

```python
@register_migration(3, "添加用戶統計表")
def migration_v3_add_user_stats(conn):
    """第三版遷移：創建用戶統計表"""
    cursor = conn.cursor()
    
    # 創建新表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS t_user_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            request_count INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 創建索引
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_stats_user_id 
        ON t_user_stats(user_id)
    """)
    
    print("  ✅ 已創建用戶統計表")
```

### 2. 遷移函數規範

- **版本號**：必須是唯一的整數，建議遞增
- **描述**：簡短說明遷移的目的
- **函數名**：使用 `migration_v{版本號}_{功能描述}` 格式
- **錯誤處理**：使用異常來報告錯誤，系統會自動回滾

### 3. 常見遷移操作

#### 添加新欄位
```python
cursor.execute("ALTER TABLE t_table_name ADD COLUMN new_column TEXT DEFAULT ''")
```

#### 創建新表
```python
cursor.execute("""
    CREATE TABLE IF NOT EXISTS t_new_table (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        field1 TEXT NOT NULL,
        field2 INTEGER DEFAULT 0
    )
""")
```

#### 修改資料
```python
cursor.execute("UPDATE t_table_name SET field = ? WHERE condition = ?", (value, condition))
```

#### 創建索引
```python
cursor.execute("CREATE INDEX IF NOT EXISTS idx_name ON t_table(column)")
```

## 手動執行遷移

### 在容器外執行
```bash
# 自動執行（透過 dev-deploy.sh）
./dev-deploy.sh -m rebuild

# 手動執行遷移腳本
docker exec gemini-balance python /app/migrations/migration_manager.py
```

### 在容器內執行
```bash
# 進入容器
docker exec -it gemini-balance bash

# 執行遷移
python /app/migrations/migration_manager.py

# 查看遷移歷史
sqlite3 /app/data/gemini.db "SELECT * FROM t_migration_history"
```

## 遷移歷史表

系統會自動創建 `t_migration_history` 表來追蹤遷移狀態：

| 欄位 | 類型 | 說明 |
|------|------|------|
| version | INTEGER | 遷移版本號（主鍵） |
| description | TEXT | 遷移描述 |
| applied_at | TIMESTAMP | 應用時間 |
| status | TEXT | 狀態（success/failed） |

## 注意事項

1. **備份資料**：執行遷移前建議備份資料庫
2. **測試環境**：先在測試環境驗證遷移腳本
3. **版本號唯一**：確保每個遷移的版本號不重複
4. **原子性操作**：每個遷移應該是獨立的原子操作
5. **向下相容**：考慮舊版本的相容性

## 疑難排解

### 遷移失敗
- 檢查錯誤信息：`docker logs gemini-balance`
- 查看遷移歷史：`sqlite3 data/gemini.db "SELECT * FROM t_migration_history"`
- 手動修復後重試

### 回滾遷移
目前系統不支援自動回滾，如需回滾請：
1. 手動恢復資料庫備份
2. 或編寫反向遷移腳本

### 跳過特定遷移
如需跳過某個有問題的遷移：
1. 手動插入成功記錄到 `t_migration_history`
2. 或在遷移函數中添加條件判斷