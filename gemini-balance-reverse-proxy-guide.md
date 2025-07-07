# Gemini Balance 反向代理設置指南

本指南將教你如何設置本地反向代理，讓應用程式以為在連接 Google Gemini API (`https://generativelanguage.googleapis.com/`)，但實際上請求會被轉發到你的 Gemini Balance 服務。

## 目錄
- [使用場景](#使用場景)
- [OpenAI 相容格式支援](#openai-相容格式支援)
- [前置需求](#前置需求)
- [快速設置](#快速設置)
- [詳細步驟](#詳細步驟)
- [使用方法](#使用方法)
- [管理腳本](#管理腳本)
- [疑難排解](#疑難排解)
- [安全注意事項](#安全注意事項)

## 使用場景

- 開發環境中測試 Gemini API
- 使用 Gemini Balance 服務管理 API 配額
- 避免直接暴露真實的 Google API 密鑰
- 本地開發不想修改應用程式代碼

## OpenAI 相容格式支援

除了 Gemini 原生格式外，透過反向代理設置，你還可以使用 OpenAI 相容格式來呼叫 Gemini API。這對於已經使用 OpenAI SDK 或格式的應用程式特別有用。

**端點對應：**
- Gemini 原生格式：`/v1beta/models/{model}:generateContent`
- OpenAI 相容格式：`/v1beta/chat/completions` → 自動重寫為 `/hf/v1/chat/completions`

**認證方式差異：**
- Gemini 原生：使用 `x-goog-api-key` header
- OpenAI 相容：使用 `Authorization: Bearer` header

## 前置需求

### Linux / WSL2
- Ubuntu/Debian 系統（WSL2 也可以）
- Gemini Balance 服務已運行（預設端口 8000，可自定義）
- sudo 權限

### Windows
- Windows 10/11
- Gemini Balance 服務已運行（預設端口 8000，可自定義）
- 管理員權限
- Chocolatey 或 Scoop 包管理器（用於安裝工具）


## 快速設置

### Linux / WSL2
```bash
# 1. 安裝必要套件
sudo apt update && sudo apt install -y nginx

# 2. 按照下方詳細步驟進行設置

# 3. 測試（使用自簽名證書需要加 -k）
curl -X POST "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent" \
  -H "Content-Type: application/json" \
  -H "x-goog-api-key: YOUR_AUTH_TOKEN" \
  -d '{"contents": [{"role": "user", "parts": [{"text": "Hello!"}]}]}'
```

### Windows
```powershell
# 1. 安裝 mkcert 和下載 nginx
# 使用 Chocolatey
choco install mkcert -y
# 或使用 Scoop
scoop install mkcert

# 2. 下載 nginx for Windows
# 從 http://nginx.org/en/download.html 下載並解壓到 C:\nginx

# 3. 按照下方詳細步驟進行設置

# 4. 測試
Invoke-RestMethod -Uri "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent" `
  -Method Post -Headers @{"Content-Type"="application/json"; "x-goog-api-key"="YOUR_AUTH_TOKEN"} `
  -Body '{"contents":[{"role":"user","parts":[{"text":"Hello!"}]}]}'
```

## 詳細步驟

選擇你的平台：
- [Linux / WSL2 設置](#linux--wsl2-設置)
- [Windows 設置](#windows-設置)

---

## Linux / WSL2 設置

### 1. 確認 Gemini Balance 服務

首先確認你的 Gemini Balance 運行在哪個端口：
```bash
# Docker 用戶
docker ps | grep gemini-balance

# 或檢查 docker-compose.yml
grep -A2 "ports:" docker-compose.yml

# 預設應該是 8000:8000
```

### 2. 安裝 Nginx

```bash
sudo apt update
sudo apt install -y nginx
```

### 3. 生成 SSL 證書

#### 選項 A：自簽名證書（快速）
```bash
sudo mkdir -p /etc/nginx/ssl
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/nginx/ssl/googleapis.key \
  -out /etc/nginx/ssl/googleapis.crt \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=generativelanguage.googleapis.com"
```

#### 選項 B：使用 mkcert（推薦）
```bash
# 安裝 mkcert
curl -L https://github.com/FiloSottile/mkcert/releases/download/v1.4.4/mkcert-v1.4.4-linux-amd64 -o mkcert
chmod +x mkcert
sudo mv mkcert /usr/local/bin/

# 設置本地 CA
mkcert -install

# 生成證書
mkcert generativelanguage.googleapis.com
sudo mv generativelanguage.googleapis.com*.pem /etc/nginx/ssl/
```

**重要：設置 Node.js 信任 mkcert CA**

如果你使用基於 Node.js 的工具（如 gemini-cli，實際執行命令為 `gemini`），需要額外設置：

```bash
# 將 mkcert CA 路徑加入環境變數
echo "export NODE_EXTRA_CA_CERTS=\"$(mkcert -CAROOT)/rootCA.pem\"" >> ~/.bashrc
echo "export NODE_EXTRA_CA_CERTS=\"$(mkcert -CAROOT)/rootCA.pem\"" >> ~/.zshrc
echo "set -x NODE_EXTRA_CA_CERTS \"$(mkcert -CAROOT)/rootCA.pem\"" >> ~/.config/fish/config.fish

# 立即生效
source ~/.bashrc  # 如果使用 bash
source ~/.zshrc  # 如果使用 zsh
source ~/.config/fish/config.fish  # 如果使用 fish
```

### 4. 配置 Nginx

創建配置文件時，記得替換端口號：

```bash
# 創建配置文件
sudo tee /etc/nginx/sites-available/googleapis-proxy > /dev/null << EOF
server {
    listen 443 ssl;
    server_name generativelanguage.googleapis.com;
    
    # 如果使用自簽名證書
    ssl_certificate /etc/nginx/ssl/googleapis.crt;
    ssl_certificate_key /etc/nginx/ssl/googleapis.key;
    # 如果使用 mkcert 證書（取消下面的註釋並註釋上面兩行）
    # ssl_certificate /etc/nginx/ssl/generativelanguage.googleapis.com.pem;
    # ssl_certificate_key /etc/nginx/ssl/generativelanguage.googleapis.com-key.pem;
    
    # SSL 配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    
    # 重寫 OpenAI 相容端點 (v1beta 路徑)
    location /v1beta/chat/completions {
        rewrite ^/v1beta/chat/completions$ /hf/v1/chat/completions break;
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Access-Control-Allow-Origin "*";
        proxy_set_header Access-Control-Allow-Methods "GET, POST, OPTIONS";
        proxy_set_header Access-Control-Allow-Headers "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization";
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # 處理 CORS
        proxy_set_header Access-Control-Allow-Origin "*";
        proxy_set_header Access-Control-Allow-Methods "GET, POST, OPTIONS";
        proxy_set_header Access-Control-Allow-Headers "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization";
        
        # 超時設置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}

# HTTP 配置（可選，用於不支持 HTTPS 的場景）
server {
    listen 80;
    server_name generativelanguage.googleapis.com;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
```

啟用配置：
```bash
sudo ln -s /etc/nginx/sites-available/googleapis-proxy /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 5. 修改 hosts 文件

```bash
# 備份原始 hosts
sudo cp /etc/hosts /etc/hosts.backup.$(date +%Y%m%d_%H%M%S)

# 添加解析記錄
echo "127.0.0.1 generativelanguage.googleapis.com" | sudo tee -a /etc/hosts
```

---

## Windows 設置

### 1. 確認 Gemini Balance 服務

確認你的 Gemini Balance 運行在哪個端口：
```powershell
# Docker 用戶
docker ps | Select-String gemini-balance

# 檢查端口（預設應該是 8000，如果使用 docker-compose.reverse-proxy.yml 則是 9527）
```

### 2. 安裝必要工具

#### 安裝 mkcert（生成受信任的 SSL 證書）
```powershell
# 使用 Chocolatey
choco install mkcert -y

# 或使用 Scoop
scoop install mkcert
```

#### 下載 nginx for Windows
- 從 [nginx.org](http://nginx.org/en/download.html) 下載 Windows 版本
- 解壓到 `C:\nginx`

### 3. 生成 SSL 證書

```powershell
# 安裝 CA 到 Windows 證書存儲
mkcert -install

# 創建證書目錄
mkdir C:\nginx\ssl

# 生成證書
cd C:\nginx\ssl
mkcert generativelanguage.googleapis.com
```

這會生成兩個文件：
- `generativelanguage.googleapis.com.pem`（證書）
- `generativelanguage.googleapis.com-key.pem`（私鑰）

### 4. 配置 nginx

創建 `C:\nginx\conf\nginx.conf`：

```nginx
worker_processes 1;

events {
    worker_connections 1024;
}

http {
    server {
        listen 443 ssl;
        server_name generativelanguage.googleapis.com;
        
        # SSL 證書（使用 mkcert 生成的）
        ssl_certificate C:/nginx/ssl/generativelanguage.googleapis.com.pem;
        ssl_certificate_key C:/nginx/ssl/generativelanguage.googleapis.com-key.pem;
        
        # SSL 設定
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;
        
        # 日誌
        access_log logs/googleapis_access.log;
        error_log logs/googleapis_error.log;
        
        # 重寫 OpenAI 相容端點 (v1beta 路徑)
        location /v1beta/chat/completions {
            rewrite ^/v1beta/chat/completions$ /v1/chat/completions break;
            proxy_pass http://localhost:8000;  # 根據實際端口調整
            
            # 傳遞所有原始 headers
            proxy_pass_request_headers on;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
        
        location / {
            # 代理到 Gemini Balance
            proxy_pass http://localhost:8000;  # 根據實際端口調整
            
            # 傳遞所有原始 headers
            proxy_pass_request_headers on;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # 支援串流
            proxy_buffering off;
            proxy_cache off;
            proxy_read_timeout 300s;
            proxy_connect_timeout 75s;
            
            # SSE 支援
            proxy_set_header Connection '';
            proxy_http_version 1.1;
            chunked_transfer_encoding off;
        }
    }
}
```

**注意**：如果你的 Gemini Balance 運行在 9527 端口，請將所有 `localhost:8000` 改為 `localhost:9527`。

### 5. 修改 hosts 文件

以管理員身份運行 PowerShell：

```powershell
# 備份原始 hosts
Copy-Item "C:\Windows\System32\drivers\etc\hosts" "C:\Windows\System32\drivers\etc\hosts.backup.$(Get-Date -Format 'yyyyMMdd_HHmmss')"

# 添加解析記錄
Add-Content -Path "C:\Windows\System32\drivers\etc\hosts" -Value "`n127.0.0.1 generativelanguage.googleapis.com"

# 刷新 DNS 緩存
ipconfig /flushdns
```

### 6. 設置 Node.js 環境變量

對於 Node.js 應用（如 VSCode 擴展），需要信任 mkcert CA：

```powershell
# 獲取 mkcert CA 路徑
$caPath = & mkcert -CAROOT
$caFile = "$caPath\rootCA.pem"

# 設置環境變量（系統級別，需要管理員權限）
[Environment]::SetEnvironmentVariable("NODE_EXTRA_CA_CERTS", $caFile, "Machine")

# 設置用戶級別（當前用戶）
[Environment]::SetEnvironmentVariable("NODE_EXTRA_CA_CERTS", $caFile, "User")
```

**重要**：設置環境變量後，需要重啟應用程序（如 VSCode）才能生效。

### 7. 啟動 nginx

```powershell
# 啟動 nginx
cd C:\nginx
Start-Process nginx.exe -WindowStyle Hidden

# 或直接運行
C:\nginx\nginx.exe

# 檢查是否運行成功
tasklist | findstr nginx
```

## 使用方法

### 查找你的認證 Token

從 Gemini Balance 的 `.env` 文件獲取：
```bash
# 查看 AUTH_TOKEN
grep AUTH_TOKEN ./gemini-balance/.env
```

### API 調用範例

#### Linux / WSL2

**Gemini 原生格式：**
```bash
# 替換 YOUR_AUTH_TOKEN 為你的實際 token
curl -X POST "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent" \
  -H "Content-Type: application/json" \
  -H "x-goog-api-key: YOUR_AUTH_TOKEN" \
  -d '{
    "contents": [{
      "role": "user",
      "parts": [{
        "text": "你的問題"
      }]
    }]
  }'
```

**OpenAI 相容格式：**
```bash
# 使用 OpenAI 格式呼叫 Gemini
curl -X POST "https://generativelanguage.googleapis.com/v1beta/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN" \
  -d '{
    "model": "gemini-2.5-flash",
    "messages": [{
      "role": "user",
      "content": "你的問題"
    }]
  }'
```

#### Windows PowerShell

**Gemini 原生格式：**
```powershell
# 替換 YOUR_AUTH_TOKEN 為你的實際 token
Invoke-RestMethod -Uri "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent" `
  -Method Post `
  -Headers @{
    "Content-Type" = "application/json"
    "x-goog-api-key" = "YOUR_AUTH_TOKEN"
  } `
  -Body '{"contents":[{"role":"user","parts":[{"text":"你的問題"}]}]}' `
  -SkipCertificateCheck
```

**OpenAI 相容格式：**
```powershell
# 使用 OpenAI 格式呼叫 Gemini
Invoke-RestMethod -Uri "https://generativelanguage.googleapis.com/v1beta/chat/completions" `
  -Method Post `
  -Headers @{
    "Content-Type" = "application/json"
    "Authorization" = "Bearer YOUR_AUTH_TOKEN"
  } `
  -Body '{"model":"gemini-2.5-flash","messages":[{"role":"user","content":"你的問題"}]}' `
  -SkipCertificateCheck
```

### Node.js 應用程式

如果使用 mkcert 生成的證書，需要設置 Node.js 信任 mkcert CA（參見上方「設置 Node.js 信任 mkcert CA」部分）。

如果已經按照上述步驟設置但仍有問題，可以臨時使用：
```bash
# 臨時設置（僅當前會話）
export NODE_EXTRA_CA_CERTS="$(mkcert -CAROOT)/rootCA.pem"

# 或者使用自簽名證書時的臨時解決方案（不推薦）
NODE_TLS_REJECT_UNAUTHORIZED=0 gemini [你的命令]
```

### Python 應用程式

**Gemini 原生格式：**
```python
import requests
import urllib3

# 禁用 SSL 警告（開發環境）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

response = requests.post(
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
    headers={
        "Content-Type": "application/json",
        "x-goog-api-key": "YOUR_AUTH_TOKEN"
    },
    json={
        "contents": [{
            "role": "user",
            "parts": [{"text": "Hello!"}]
        }]
    },
    verify=False  # 開發環境忽略證書
)
```

**OpenAI 相容格式：**
```python
# 使用 OpenAI SDK
from openai import OpenAI

# 設置 base_url 指向代理服務器
client = OpenAI(
    api_key="YOUR_AUTH_TOKEN",
    base_url="https://generativelanguage.googleapis.com/v1beta",
    http_client=httpx.Client(verify=False)  # 開發環境忽略證書
)

response = client.chat.completions.create(
    model="gemini-2.5-flash",
    messages=[
        {"role": "user", "content": "Hello!"}
    ]
)

# 或使用 requests
response = requests.post(
    "https://generativelanguage.googleapis.com/v1beta/chat/completions",
    headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer YOUR_AUTH_TOKEN"
    },
    json={
        "model": "gemini-2.5-flash",
        "messages": [{"role": "user", "content": "Hello!"}]
    },
    verify=False  # 開發環境忽略證書
)
```

## 管理腳本

### Linux / WSL2 腳本

#### 1. 切換開關腳本

創建 `toggle-google-api-proxy.sh`：
```bash
#!/bin/bash
if grep -q "^127.0.0.1 generativelanguage.googleapis.com" /etc/hosts; then
    echo "關閉代理..."
    sudo sed -i 's/^127.0.0.1 generativelanguage.googleapis.com/# 127.0.0.1 generativelanguage.googleapis.com/' /etc/hosts
    echo "✓ 代理已關閉 - 現在連接到真實的 Google API"
else
    echo "開啟代理..."
    sudo sed -i 's/^# 127.0.0.1 generativelanguage.googleapis.com/127.0.0.1 generativelanguage.googleapis.com/' /etc/hosts
    echo "✓ 代理已開啟 - 現在連接到 Gemini Balance (localhost:8000)"
fi
```

#### 2. 更新端口腳本

如果需要更改端口，創建 `update-proxy-port.sh`：
```bash
#!/bin/bash
if [ -z "$1" ]; then
    echo "用法: $0 <新端口號>"
    exit 1
fi

NEW_PORT=$1
echo "更新端口從 8000 到 $NEW_PORT..."
sudo sed -i "s/:8000/:$NEW_PORT/g" /etc/nginx/sites-available/googleapis-proxy
sudo nginx -t && sudo systemctl reload nginx
echo "✓ 端口已更新！"
```

#### 3. 完整移除腳本

創建 `remove-google-api-proxy-completely.sh`：
```bash
#!/bin/bash
# 還原 hosts
if ls /etc/hosts.backup.* 1> /dev/null 2>&1; then
    latest_backup=$(ls -t /etc/hosts.backup.* | head -1)
    sudo cp "$latest_backup" /etc/hosts
fi

# 移除 nginx 配置
sudo rm -f /etc/nginx/sites-enabled/googleapis-proxy
sudo rm -f /etc/nginx/sites-available/googleapis-proxy

# 移除證書
sudo rm -rf /etc/nginx/ssl/googleapis.*
sudo rm -rf /etc/nginx/ssl/generativelanguage.googleapis.com*

# 重啟 nginx
sudo systemctl restart nginx
echo "代理已完全移除！"
```

### Windows 腳本

#### 1. 啟動/停止 nginx

創建 `C:\nginx\start-nginx.ps1`：
```powershell
# 啟動 nginx
$nginxPath = "C:\nginx\nginx.exe"
if (Test-Path $nginxPath) {
    Start-Process $nginxPath -WindowStyle Hidden
    Write-Host "nginx 已啟動" -ForegroundColor Green
} else {
    Write-Host "找不到 nginx.exe" -ForegroundColor Red
}
```

創建 `C:\nginx\stop-nginx.ps1`：
```powershell
# 停止 nginx
$nginxProcess = Get-Process nginx -ErrorAction SilentlyContinue
if ($nginxProcess) {
    Stop-Process -Name nginx -Force
    Write-Host "nginx 已停止" -ForegroundColor Yellow
} else {
    Write-Host "nginx 未運行" -ForegroundColor Gray
}
```

創建 `C:\nginx\reload-nginx.ps1`：
```powershell
# 重新載入 nginx 配置
C:\nginx\nginx.exe -s reload
Write-Host "nginx 配置已重新載入" -ForegroundColor Green
```

#### 2. 切換開關腳本

創建 `C:\nginx\toggle-hosts.ps1`：
```powershell
# Toggle hosts file entry for generativelanguage.googleapis.com
$hostsPath = "C:\Windows\System32\drivers\etc\hosts"
$content = Get-Content $hostsPath

# Check if the line is active or commented
$activeLine = $content | Where-Object { $_ -match "^127\.0\.0\.1\s+generativelanguage\.googleapis\.com" }
$commentedLine = $content | Where-Object { $_ -match "^#\s*127\.0\.0\.1\s+generativelanguage\.googleapis\.com" }

if ($activeLine) {
    # Comment out the active line
    $content = $content -replace '^127\.0\.0\.1\s+generativelanguage\.googleapis\.com', '# 127.0.0.1 generativelanguage.googleapis.com'
    Write-Host "Disabled proxy - Gemini Balance can now connect to real Google API" -ForegroundColor Yellow
} elseif ($commentedLine) {
    # Uncomment the line
    $content = $content -replace '^#\s*127\.0\.0\.1\s+generativelanguage\.googleapis\.com', '127.0.0.1 generativelanguage.googleapis.com'
    Write-Host "Enabled proxy - Requests will go through Caddy to Gemini Balance" -ForegroundColor Green
} else {
    Write-Host "No entry found for generativelanguage.googleapis.com" -ForegroundColor Red
}

# Save the file (requires admin rights)
try {
    $content | Set-Content $hostsPath
    Write-Host "Successfully updated hosts file" -ForegroundColor Green
    
    # Flush DNS cache
    ipconfig /flushdns | Out-Null
    Write-Host "DNS cache flushed" -ForegroundColor Green
} catch {
    Write-Host "Error: Please run as Administrator" -ForegroundColor Red
    Write-Host $_.Exception.Message
}
```

#### 3. API 測試工具

創建 `C:\nginx\test-proxy.ps1`：
```powershell
# 測試代理設置
param(
    [string]$Token = "YOUR_AUTH_TOKEN"
)

Write-Host "測試反向代理設置..." -ForegroundColor Cyan

# 忽略 SSL 證書檢查（如果需要）
[System.Net.ServicePointManager]::ServerCertificateValidationCallback = {$true}

# 測試基本連接
try {
    $response = Invoke-RestMethod -Uri "https://generativelanguage.googleapis.com/v1beta/models" `
        -Headers @{"x-goog-api-key" = $Token}
    Write-Host "✓ 基本連接成功" -ForegroundColor Green
} catch {
    Write-Host "✗ 連接失敗: $_" -ForegroundColor Red
}

# 測試 OpenAI 相容格式
try {
    $body = @{
        model = "gemini-2.5-flash"
        messages = @(@{role = "user"; content = "Hello"})
    } | ConvertTo-Json
    
    $response = Invoke-RestMethod -Uri "https://generativelanguage.googleapis.com/v1beta/chat/completions" `
        -Method Post `
        -Headers @{
            "Content-Type" = "application/json"
            "Authorization" = "Bearer $Token"
        } `
        -Body $body
    
    Write-Host "✓ OpenAI 格式測試成功" -ForegroundColor Green
} catch {
    Write-Host "✗ OpenAI 格式測試失敗: $_" -ForegroundColor Red
}
```

創建 `C:\nginx\test-api.ps1` 用於詳細測試：
```powershell
# 完整 API 測試
param(
    [string]$Token = "YOUR_AUTH_TOKEN",
    [switch]$TestMaxTokens
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Gemini Balance API 測試" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 測試函數
function Test-API {
    param(
        [string]$Name,
        [string]$Uri,
        [hashtable]$Headers,
        [string]$Body
    )
    
    Write-Host "`n測試: $Name" -ForegroundColor Yellow
    try {
        $response = Invoke-WebRequest -Uri $Uri -Method Post `
            -Headers $Headers -Body $Body -UseBasicParsing
        
        if ($response.StatusCode -eq 200) {
            Write-Host "✓ 成功 (200)" -ForegroundColor Green
            $content = $response.Content | ConvertFrom-Json
            if ($content.choices) {
                Write-Host "  回應: $($content.choices[0].message.content.Substring(0, 50))..." -ForegroundColor Gray
            }
        }
    } catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        Write-Host "✗ 失敗 ($statusCode): $($_.Exception.Message)" -ForegroundColor Red
    }
}

# 測試不同場景
$tests = @(
    @{
        Name = "基本請求"
        Body = @{
            model = "gemini-2.5-flash"
            messages = @(@{role = "user"; content = "Say hello"})
        }
    }
)

if ($TestMaxTokens) {
    $tests += @{
        Name = "帶 max_tokens 的請求"
        Body = @{
            model = "gemini-2.5-flash"
            messages = @(@{role = "user"; content = "Tell me a story"})
            max_tokens = 100
        }
    }
}

foreach ($test in $tests) {
    Test-API -Name $test.Name `
        -Uri "https://generativelanguage.googleapis.com/v1beta/chat/completions" `
        -Headers @{
            "Content-Type" = "application/json"
            "Authorization" = "Bearer $Token"
        } `
        -Body ($test.Body | ConvertTo-Json)
}

Write-Host "`n測試完成！" -ForegroundColor Cyan
```

## 疑難排解

### 1. VSCode 擴展或其他應用返回錯誤

**問題 A**：含有 `max_tokens` 參數的請求返回 500 錯誤
**解決**：這是 Gemini Balance 的已知問題，需要修復 `response_handler.py` 文件中的 'parts' 錯誤。

**問題 B**：SSL 證書錯誤（`Error: self signed certificate`）
**解決**：
1. 確認已運行 `mkcert -install`
2. 檢查 NODE_EXTRA_CA_CERTS 環境變量是否設置正確
3. 重啟應用程序（如 VSCode）
4. Windows 檢查環境變量：
   ```powershell
   echo $env:NODE_EXTRA_CA_CERTS
   # 或
   [Environment]::GetEnvironmentVariable("NODE_EXTRA_CA_CERTS", "User")
   ```

**問題 C**：Authorization header 未傳遞（401 錯誤）
**解決**：確保 nginx 配置包含 `proxy_pass_request_headers on;`

### 2. 連接被拒絕

**問題**：`Connection refused`

#### Linux / WSL2 檢查：
```bash
# 確認 Gemini Balance 運行中及端口
docker ps | grep gemini-balance

# 確認 nginx 配置的端口正確
grep proxy_pass /etc/nginx/sites-available/googleapis-proxy

# 確認 nginx 運行中
sudo systemctl status nginx

# 確認 hosts 設置
grep generativelanguage.googleapis.com /etc/hosts
```

#### Windows 檢查：
```powershell
# 確認 Gemini Balance 運行中及端口
docker ps | Select-String gemini-balance

# 確認 nginx 配置的端口正確
Get-Content C:\nginx\conf\nginx.conf | Select-String "proxy_pass"

# 確認 nginx 運行中
tasklist | findstr nginx
# 或檢查端口
netstat -an | findstr :443

# 確認 hosts 設置
Get-Content C:\Windows\System32\drivers\etc\hosts | Select-String generativelanguage.googleapis.com

# 測試 nginx 配置
C:\nginx\nginx.exe -t
```

### 3. nginx 無法啟動

**問題**：443 端口被占用或配置錯誤

**解決**：
```powershell
# 檢查端口占用
netstat -an | findstr :443

# 找出占用 443 端口的進程
netstat -aon | findstr :443
# 然後使用 PID 查找進程名
tasklist | findstr "PID"

# 測試配置文件
C:\nginx\nginx.exe -t

# 查看錯誤日誌
Get-Content C:\nginx\logs\error.log -Tail 20
```

### 4. 401 未授權

**問題**：`Invalid key and missing x-goog-api-key header`

**解決**：
- 檢查 Gemini Balance 的 `.env` 文件中的 `AUTH_TOKEN`
- 確保使用正確的 header:
  - Gemini 原生格式：`x-goog-api-key: YOUR_AUTH_TOKEN`
  - OpenAI 相容格式：`Authorization: Bearer YOUR_AUTH_TOKEN`
- 確認 token 在 `ALLOWED_TOKENS` 列表中


## Docker 重要注意事項

### 避免 DNS 循環問題

當你設置了 hosts 文件將 `generativelanguage.googleapis.com` 指向本地後，Docker 容器可能會繼承主機的 DNS 設置，導致 Gemini Balance 無法連接到真正的 Google API。

**解決方案：使用自定義 DNS**

```bash
# Docker run 命令
docker run -d --name gemini-balance \
  --dns 8.8.8.8 \
  --dns 8.8.4.4 \
  -p 8000:8000 \
  -v $(pwd)/.env:/app/.env \
  gemini-balance

# 或在 docker-compose.yml 中
services:
  gemini-balance:
    image: ghcr.io/snailyp/gemini-balance:latest
    ports:
      - "8000:8000"
    dns:
      - 8.8.8.8
      - 8.8.4.4
    volumes:
      - ./.env:/app/.env
```

這樣確保容器內的 DNS 查詢會使用 Google 的公共 DNS，而不是受主機 hosts 文件影響。

## Docker Compose 範例

如果你使用 Docker Compose，完整配置如下：
```yaml
services:
  gemini-balance:
    image: ghcr.io/snailyp/gemini-balance:latest
    ports:
      - "8000:8000"  # 主機端口:容器端口
    dns:
      - 8.8.8.8      # 使用 Google DNS
      - 8.8.4.4      # 避免 hosts 文件影響
    volumes:
      - ./.env:/app/.env
```

記住：
- nginx/Caddy 代理要指向**主機端口**（冒號前的數字）
- 容器必須使用外部 DNS 才能正確連接到 Google API

## 安全注意事項

⚠️ **重要提醒**：
- 這個設置僅適用於**開發環境**
- 不要在生產環境使用自簽名證書
- 定期更新證書避免過期
- 保護好你的 API 密鑰和認證 Token

---

💡 **提示**：完成設置後，你的應用程式無需修改任何代碼，就可以透過 Gemini Balance 使用 Google Gemini API！