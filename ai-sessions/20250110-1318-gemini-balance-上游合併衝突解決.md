# gemini-balance 上游合併衝突解決

## 標題
gemini-balance 上游合併衝突解決

## 原因
GitHub Actions 的 sync-upstream workflow 在嘗試同步上游 snailyp/gemini-balance 時遇到合併衝突，需要手動解決。專案已經有一個詳細的 MERGE_CONFLICTS_TODO.md 文件指導解決流程。

## 過程

### 1. 環境準備與分析
- 確認當前在 main 分支，並已配置好 origin 和 upstream remotes
- 創建備份分支 `backup-before-merge-20250110` 以防萬一
- 分析上游有 13 個新提交，包括 TTS 功能、token 計數 API、自定義 headers 等新功能

### 2. 衝突文件分析與解決策略討論

**app/core/constants.py**
- 本地：新增 RPM 限制相關常量
- 上游：新增 TTS_VOICE_NAMES 列表
- 決策：保留雙方新增內容（A 方案）

**app/router/gemini_routes.py**
- 本地：有 RPM 感知的 key 獲取和模型名稱轉換
- 上游：更簡潔的實現但缺少 RPM 功能
- 決策：保留本地版本以維持 RPM 功能（A 方案）

**app/service/client/api_client.py**
- 本地：沒有自定義 headers 支持
- 上游：新增了自定義 headers 功能
- 決策：採用上游版本獲得新功能（B 方案），經檢查確認安全

**app/service/key/key_manager.py**
- 本地：使用索引方式管理 key 循環
- 上游：使用 Python itertools.cycle
- 決策：保留本地索引實現，更易於調試和狀態管理

### 3. 技術驗證
- 執行多種編譯測試確保沒有語法錯誤
- AST 解析驗證
- 模組導入測試
- 確認無殘留衝突標記

### 4. 完成合併
- 標記已解決的衝突文件
- 創建詳細的 merge commit
- 成功推送到 origin

### 5. 後續處理
- 使用 gh CLI 啟用 repository 的 Issues 功能，避免 workflow 報錯

## 結果

### 成功整合的新功能
- ✅ TTS 語音名稱支持（30 個預定義語音）
- ✅ Token 計數端點 (`count_tokens`)
- ✅ 自定義 HTTP headers 支持
- ✅ JSON Schema 清理功能
- ✅ 調試日誌改進
- ✅ Vertex API 更名為 Vertex Express API

### 保留的本地功能
- ✅ RPM (Requests Per Minute) 限制功能
- ✅ 模型名稱轉換功能
- ✅ 索引式 key 管理（相比 cycle 更易控制）

### 行動項目
- [已完成] 啟用 GitHub Issues 功能
- [可選] 未來可考慮修復 sync-upstream.yml workflow

## 相關檔案
- `MERGE_CONFLICTS_TODO.md` - 合併指南文件
- `app/core/constants.py` - 常量定義
- `app/router/gemini_routes.py` - API 路由
- `app/service/client/api_client.py` - API 客戶端
- `app/service/key/key_manager.py` - API key 管理
- `.github/workflows/sync-upstream.yml` - 同步 workflow

## 技術關鍵字
git, merge-conflict, upstream-sync, python, gemini-api, rpm-limiting, tts, token-counting, custom-headers, vertex-express-api, github-actions, gh-cli

## 目前分支
main

---
開始時間：2025-07-10 13:00
結束時間：2025-07-10 13:18