# Gemini Balance 智能代理系統使用指南

本指南說明如何使用已建立的 WSL nginx 智能路由系統，該系統能夠：
- 將 **gemini-2.5-pro** 請求智能路由到本地 Gemini Balance 服務
- 將**其他模型**請求透明代理到 Google API
- 同時支援 Gemini 原生格式和 OpenAI 相容格式
- 讓 Windows 和 WSL 應用程式無縫使用代理服務

## 目錄
- [系統架構概覽](#系統架構概覽)
- [Windows 應用程式支援](#windows-應用程式支援)
- [SSL 證書信任設定](#ssl-證書信任設定)
- [API 使用方法](#api-使用方法)
- [管理工具](#管理工具)
- [測試與驗證](#測試與驗證)
- [故障排除](#故障排除)
- [進階配置](#進階配置)

## 系統架構概覽

### 智能路由機制

當前系統使用 WSL nginx 實現智能路由，具有以下特性：

```
應用程式請求 → WSL nginx (443) → 智能路由決策
                                    ↓
├─ gemini-2.5-pro → localhost:9527 (Gemini Balance)
├─ OpenAI 格式 → localhost:9527 (轉換處理)
└─ 其他模型 → generativelanguage.googleapis.com (Google API)
```

### WSL 2 網路共用機制

- **端口共用**：WSL nginx 監聽 `0.0.0.0:443`，Windows 應用程式的請求自動轉發到 WSL
- **統一服務**：Windows 和 WSL 共用同一個 nginx 實例，避免配置重複和端口衝突
- **透明代理**：應用程式無需修改，直接使用 `https://generativelanguage.googleapis.com/`

### 使用場景

- **開發環境**：本地測試 Gemini API 而不消耗 Google 配額
- **生產環境**：智能分流，重度模型使用本地服務，輕量模型使用官方 API
- **應用遷移**：既有應用程式無需修改程式碼，直接獲得路由功能
- **成本最佳化**：gemini-2.5-pro 使用免費本地服務，其他模型按需使用付費 API

## Windows 應用程式支援

### 核心配置需求

要讓 Windows 應用程式（如 VSCode、PowerShell、Python 腳本）正常使用代理服務，需要完成以下配置：

1. **Hosts 檔案設定**：已通過管理腳本自動配置
2. **SSL 證書信任**：需要匯入 mkcert 根 CA 證書
3. **應用程式重啟**：完成證書配置後重啟相關應用

### 支援的 API 格式

**Gemini 原生格式：**
```http
POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent
Content-Type: application/json
x-goog-api-key: YOUR_AUTH_TOKEN
```

**OpenAI 相容格式：**
```http
POST https://generativelanguage.googleapis.com/v1beta/chat/completions
Content-Type: application/json
Authorization: Bearer YOUR_AUTH_TOKEN
```

系統會自動將 OpenAI 格式請求重寫為 `/hf/v1/chat/completions` 並轉發到本地服務處理。

## SSL 證書信任設定

### 問題背景

WSL nginx 使用 mkcert 生成的自簽名證書，Windows 應用程式預設不信任這些證書，會出現 `unable to verify the first certificate` 錯誤。

### 解決方案：匯入 mkcert 根 CA 證書

**方法 1：圖形介面匯入（推薦）**

1. 雙擊 `C:\Users\yician\mkcert-rootCA.pem`
2. 點擊 **「安裝憑證」**
3. 選擇 **「本機電腦」**（需要管理員權限）或 **「目前使用者」**
4. 選擇 **「將所有憑證放入以下的存放區」**
5. 點擊 **「瀏覽」** → 選擇 **「受信任的根憑證授權單位」**
6. 完成安裝

**方法 2：PowerShell 匯入**

```powershell
# 匯入到使用者證書存放區（不需要管理員權限）
Import-Certificate -FilePath "C:\Users\yician\mkcert-rootCA.pem" -CertStoreLocation Cert:\CurrentUser\Root

# 確認匯入成功
Get-ChildItem Cert:\CurrentUser\Root | Where-Object { $_.Subject -match "mkcert" }
```

**方法 3：使用 certmgr.msc**

1. **Win + R** → 輸入 `certmgr.msc`
2. 展開 **「受信任的根憑證授權單位」** → **「憑證」**
3. 右鍵點擊 → **「所有工作」** → **「匯入」**
4. 選擇 `C:\Users\yician\mkcert-rootCA.pem`

### Node.js 應用程式額外設定

對於 VSCode 等基於 Node.js 的應用程式，還需要設定環境變數：

```powershell
# 設定 Node.js 信任 mkcert CA
[Environment]::SetEnvironmentVariable("NODE_EXTRA_CA_CERTS", "C:\Users\yician\mkcert-rootCA.pem", "User")

# 重新啟動 VSCode 或其他 Node.js 應用程式
```


## API 使用方法

### 獲取認證 Token

從 Gemini Balance 的 `.env` 檔案獲取 `AUTH_TOKEN`：

```bash
# 查看可用的認證 token
grep -E "(AUTH_TOKEN|ALLOWED_TOKENS)" /home/yician/github/gemini-balance/.env
```

### 使用範例

**Gemini 原生格式（PowerShell）：**

```powershell
# gemini-2.5-pro → 本地服務
Invoke-RestMethod -Uri "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent" `
  -Method Post `
  -Headers @{
    "Content-Type" = "application/json"
    "x-goog-api-key" = "YOUR_AUTH_TOKEN"
  } `
  -Body '{"contents":[{"parts":[{"text":"你好！請介紹你自己。"}]}]}'

# gemini-2.5-flash → Google API
Invoke-RestMethod -Uri "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent" `
  -Method Post `
  -Headers @{
    "Content-Type" = "application/json"
    "x-goog-api-key" = "YOUR_AUTH_TOKEN"
  } `
  -Body '{"contents":[{"parts":[{"text":"你好！請介紹你自己。"}]}]}'
```

**OpenAI 相容格式（PowerShell）：**

```powershell
# 使用 OpenAI 格式呼叫 Gemini → 本地服務
Invoke-RestMethod -Uri "https://generativelanguage.googleapis.com/v1beta/chat/completions" `
  -Method Post `
  -Headers @{
    "Content-Type" = "application/json"
    "Authorization" = "Bearer YOUR_AUTH_TOKEN"
  } `
  -Body '{"model":"gemini-2.5-pro","messages":[{"role":"user","content":"你好！請介紹你自己。"}]}'
```

**Python 範例：**

```python
import requests

# Gemini 原生格式
response = requests.post(
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent",
    headers={
        "Content-Type": "application/json",
        "x-goog-api-key": "YOUR_AUTH_TOKEN"
    },
    json={
        "contents": [{"parts": [{"text": "你好！請介紹你自己。"}]}]
    },
    verify=False  # 如果還沒完成證書設定
)

# OpenAI 相容格式
from openai import OpenAI
client = OpenAI(
    api_key="YOUR_AUTH_TOKEN",
    base_url="https://generativelanguage.googleapis.com/v1beta"
)

response = client.chat.completions.create(
    model="gemini-2.5-pro",
    messages=[{"role": "user", "content": "你好！請介紹你自己。"}]
)
```

## 管理工具

系統提供了完整的 PowerShell 管理工具用於 Windows 環境。

### Windows Hosts 檔案管理

**位置：** `local-proxy-management/scripts/windows/manage-windows-hosts.ps1`

```powershell
# 啟用代理（將 generativelanguage.googleapis.com 指向 127.0.0.1）
.\manage-windows-hosts.ps1 enable

# 停用代理（還原正常 DNS 解析）
.\manage-windows-hosts.ps1 disable

# 查看目前狀態
.\manage-windows-hosts.ps1 status

# 自動切換（啟用⇄停用）
.\manage-windows-hosts.ps1 toggle
```

功能特性：
- 自動備份 hosts 檔案
- 智能清理重複條目
- 正確的 Windows CRLF 編碼
- 自動 DNS 快取清理

### API 測試工具

**位置：** `local-proxy-management/scripts/windows/test-gemini-api.ps1`

```powershell
# 完整測試三個核心模型的路由
.\test-gemini-api.ps1

# 使用自定義 API key
.\test-gemini-api.ps1 -ApiKey "YOUR_AUTH_TOKEN"

# 顯示詳細錯誤訊息
.\test-gemini-api.ps1 -Verbose
```

測試內容：
- **gemini-2.5-pro**: 應路由到本地服務 (localhost:9527)
- **gemini-2.5-flash**: 應路由到 Google API
- **gemini-2.5-flash-lite-preview-06-17**: 應路由到 Google API

功能特性：
- 網路連接檢查和 DNS 解析驗證
- 智能路由來源識別（通過回應時間分析）
- SSL 證書驗證檢查
- 詳細的錯誤診斷和建議

## 測試與驗證

### 基本連接測試

在完成 SSL 證書設定後，可以進行以下測試：

```powershell
# 測試基本連接
$headers = @{"x-goog-api-key" = "YOUR_AUTH_TOKEN"}
Invoke-RestMethod -Uri "https://generativelanguage.googleapis.com/v1beta/models" -Headers $headers

# 測試 gemini-2.5-pro 路由（應路由到本地服務）
Invoke-RestMethod -Uri "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent" `
  -Method Post -Headers @{"Content-Type"="application/json"; "x-goog-api-key"="YOUR_AUTH_TOKEN"} `
  -Body '{"contents":[{"parts":[{"text":"Hello!"}]}]}'
```

### 路由驗證

測試不同模型的路由行為：

```bash
# 在 WSL 中檢查 nginx 日誌
sudo tail -f /var/log/nginx/access.log

# 另一個終端進行 API 測試
curl -X POST "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent" \
  -H "Content-Type: application/json" \
  -H "x-goog-api-key: YOUR_AUTH_TOKEN" \
  -d '{"contents":[{"parts":[{"text":"Hello!"}]}]}' \
  -k  # 如果證書尚未完全設定
```

你應該在日誌中看到：
- gemini-2.5-pro 請求轉發到 `localhost:9527`
- 其他模型請求轉發到 Google API

### VSCode 擴充功能測試

在完成 SSL 證書設定後：

1. **重新啟動 VSCode**：讓應用程式重新載入證書設定
2. **測試 Gemini 擴充功能**：嘗試使用 AI 功能，例如產生 commit 訊息
3. **檢查錯誤**：如果仍有 SSL 錯誤，檢查以下項目：
   - 證書是否正確匯入到受信任的根憑證授權單位
   - `NODE_EXTRA_CA_CERTS` 環境變數是否正確設定
   - VSCode 是否已完全重新啟動

### 效能測試

檢查系統效能和回應時間：

```bash
# 檢查 nginx 狀態
sudo systemctl status nginx

# 檢查 Gemini Balance 服務狀態
cd /home/yician/github/gemini-balance
./deploy.sh status

# 監控即時請求
sudo tail -f /var/log/nginx/access.log
```

## 故障排除

### SSL 證書問題

**問題：** `unable to verify the first certificate`

**解決步驟：**

1. **確認證書檔案存在**：
   ```powershell
   Test-Path "C:\Users\yician\mkcert-rootCA.pem"
   ```

2. **檢查證書是否已匯入**：
   ```powershell
   Get-ChildItem Cert:\CurrentUser\Root | Where-Object { $_.Subject -match "mkcert" }
   ```

3. **重新匯入證書**：
   ```powershell
   Import-Certificate -FilePath "C:\Users\yician\mkcert-rootCA.pem" -CertStoreLocation Cert:\CurrentUser\Root
   ```

4. **設定 Node.js 環境變數**：
   ```powershell
   [Environment]::SetEnvironmentVariable("NODE_EXTRA_CA_CERTS", "C:\Users\yician\mkcert-rootCA.pem", "User")
   ```

### 路由問題

**問題：** API 請求沒有按預期路由

**診斷步驟：**

1. **檢查 hosts 檔案**：
   ```powershell
   Get-Content C:\Windows\System32\drivers\etc\hosts | Select-String generativelanguage.googleapis.com
   ```

2. **檢查 nginx 配置**：
   ```bash
   # 在 WSL 中
   sudo nginx -t
   sudo systemctl status nginx
   cat /etc/nginx/sites-available/googleapis-proxy | grep -E "(location|proxy_pass)"
   ```

3. **檢查服務狀態**：
   ```bash
   # 檢查 Gemini Balance 服務
   cd /home/yician/github/gemini-balance
   ./deploy.sh status
   
   # 檢查端口監聽
   sudo netstat -tlnp | grep -E "(443|9527)"
   ```

### 連接問題

**問題：** `Connection refused` 或 `timeout`

**診斷步驟：**

1. **檢查服務狀態**：
   ```bash
   # WSL 中檢查 nginx
   sudo systemctl status nginx
   sudo netstat -tlnp | grep 443
   
   # 檢查 Gemini Balance
   cd /home/yician/github/gemini-balance
   ./deploy.sh status
   docker ps | grep gemini-balance
   ```

2. **檢查網路連接**：
   ```powershell
   # Windows 中測試
   Test-NetConnection -ComputerName generativelanguage.googleapis.com -Port 443
   nslookup generativelanguage.googleapis.com
   ```

3. **重新啟動服務**：
   ```bash
   # 重啟 nginx
   sudo systemctl restart nginx
   
   # 重啟 Gemini Balance
   cd /home/yician/github/gemini-balance
   ./deploy.sh restart
   ```

### 權限問題

**問題：** `Access is denied` 或 `401 Unauthorized`

**解決方法：**

1. **檢查 API Token**：
   ```bash
   # 查看可用的 token
   grep -E "(AUTH_TOKEN|ALLOWED_TOKENS)" /home/yician/github/gemini-balance/.env
   ```

2. **驗證 token 有效性**：
   ```bash
   # 直接測試本地服務
   curl -X POST "http://localhost:9527/v1beta/models/gemini-2.5-pro:generateContent" \
     -H "Content-Type: application/json" \
     -H "x-goog-api-key: YOUR_AUTH_TOKEN" \
     -d '{"contents":[{"parts":[{"text":"Hello!"}]}]}'
   ```

3. **更新配置**：
   ```bash
   # 修改 .env 檔案後重啟服務
   cd /home/yician/github/gemini-balance
   ./deploy.sh restart
   ```

## 進階配置

### 翻查實際 nginx 配置

目前使用的 WSL nginx 配置位於 `/etc/nginx/sites-available/googleapis-proxy`：

```bash
# 查看完整配置
sudo cat /etc/nginx/sites-available/googleapis-proxy

# 檢查關鍵路由規則
sudo grep -A 5 -E "(location|proxy_pass)" /etc/nginx/sites-available/googleapis-proxy
```

### 自定義路由規則

如果需要修改路由規則，可以編輯 nginx 配置：

```bash
# 備份配置
sudo cp /etc/nginx/sites-available/googleapis-proxy /etc/nginx/sites-available/googleapis-proxy.backup

# 編輯配置
sudo nano /etc/nginx/sites-available/googleapis-proxy

# 測試配置
sudo nginx -t

# 套用新配置
sudo systemctl reload nginx
```

### 日誌與監控

```bash
# 即時監控 nginx 訪問日誌
sudo tail -f /var/log/nginx/access.log

# 查看 nginx 錯誤日誌
sudo tail -f /var/log/nginx/error.log

# 監控 Gemini Balance 日誌
cd /home/yician/github/gemini-balance
docker logs -f gemini-balance
```

### 效能最佳化

如果需要最佳化效能，可以考慮：

1. **調整 nginx worker 數量**
2. **啟用 nginx 快取**
3. **最佳化 Gemini Balance 配置**
4. **監控系統資源使用**

---

⚠️ **重要提醒**：
- 這個設置僅適用於**開發環境**
- 生產環境中請使用正式的 SSL 證書
- 定期更新證書避免過期
- 保護好你的 API 密鑰和認證 Token

💡 **提示**：完成設置後，你的應用程式無需修改任何代碼，就可以透過 Gemini Balance 使用 Google Gemini API！