# Gemini Balance 反向代理設置指南

本指南將教你如何設置本地反向代理，讓應用程式以為在連接 Google Gemini API (`https://generativelanguage.googleapis.com/`)，但實際上請求會被轉發到你的 Gemini Balance 服務。

## 目錄
- [使用場景](#使用場景)
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

## 前置需求

- Ubuntu/Debian 系統（WSL2 也可以）
- Gemini Balance 服務已運行（預設端口 8000，可自定義）
- sudo 權限


## 快速設置

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

## 詳細步驟

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

## 使用方法

### 查找你的認證 Token

從 Gemini Balance 的 `.env` 文件獲取：
```bash
# 查看 AUTH_TOKEN
grep AUTH_TOKEN ./gemini-balance/.env
```

### API 調用範例

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

## 管理腳本

### 1. 切換開關腳本

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

### 2. 更新端口腳本

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

### 3. 完整移除腳本

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

## 疑難排解

### 1. Node.js 應用程式 SSL 證書錯誤

**問題**：`Error: self signed certificate` 或 `unable to verify the first certificate`

**解決方案**：
1. 確認已按照「設置 Node.js 信任 mkcert CA」步驟設置環境變數
2. 檢查環境變數是否生效：
   ```bash
   echo $NODE_EXTRA_CA_CERTS
   # 應該顯示類似：/home/username/.local/share/mkcert/rootCA.pem
   ```
3. 如果未生效，重新載入 shell 配置或開新終端
4. 臨時解決方案（不推薦用於生產環境）：
   ```bash
   NODE_TLS_REJECT_UNAUTHORIZED=0 你的命令
   ```

### 2. 連接被拒絕

**問題**：`Connection refused`

**檢查**：
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

### 3. 401 未授權

**問題**：`Invalid key and missing x-goog-api-key header`

**解決**：
- 檢查 Gemini Balance 的 `.env` 文件中的 `AUTH_TOKEN`
- 確保使用正確的 header: `x-goog-api-key: YOUR_AUTH_TOKEN`
- 確認 token 在 `ALLOWED_TOKENS` 列表中


## Docker Compose 範例

如果你使用 Docker Compose，配置可能如下：
```yaml
services:
  gemini-balance:
    image: ghcr.io/snailyp/gemini-balance:latest
    ports:
      - "8000:8000"  # 主機端口:容器端口
```

記住：nginx 代理要指向**主機端口**（冒號前的數字）。

## 安全注意事項

⚠️ **重要提醒**：
- 這個設置僅適用於**開發環境**
- 不要在生產環境使用自簽名證書
- 定期更新證書避免過期
- 保護好你的 API 密鑰和認證 Token

---

💡 **提示**：完成設置後，你的應用程式無需修改任何代碼，就可以透過 Gemini Balance 使用 Google Gemini API！