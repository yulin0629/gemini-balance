[Read this document in English](README_en.md) | [简体中文版](README_ZH.md)

# Gemini Balance - Gemini API 代理與負載平衡器

> 📌 **關於本專案**：這是 Fork 自 [snailyp/gemini-balance](https://github.com/snailyp/gemini-balance) 的專案。本 Fork 版本主要進行了以下加強和調整：
> 
> **🔧 新增功能：**
> - 📊 **countTokens API 支援**：新增 `/models/{model_name}:countTokens` 端點，讓你可以在發送請求前計算 token 數量
> - 🧠 **優化 thinkingConfig 處理**：智慧處理思考配置，當 thinkingBudget 設為 0 時自動省略 thinkingConfig，提高相容性
> - 📝 **完整繁體中文文件**：新增 README.md、README_zh-TW.md，使用台灣慣用技術術語
> - 🔀 **[反向代理設定指南](gemini-balance-reverse-proxy-guide.md)**：詳細說明如何設定本機反向代理，讓任何應用程式都能透過標準 Google Gemini API 端點使用 Gemini Balance
> - 🛠️ **本機開發最佳化**：提供完整的本機開發環境設定說明，包含 nginx 設定、SSL 證書生成、hosts 設定等
> 
> **🚀 加強項目：**
> - ✅ 修正原版文件中的配置錯誤和安全性問題
> - ✅ 提供更完整的疑難排解指南
> - ✅ 新增管理腳本（切換代理、更新端口、完整移除）
> - ✅ 支援 mkcert 證書生成，提供更安全的 HTTPS 設定
> - ✅ 改進 API 相容性，更好地支援各種 Gemini 模型功能
> 
> 如需查看原始專案或回報上游問題，請前往[原始儲存庫](https://github.com/snailyp/gemini-balance)。

<p align="center">
  <a href="https://trendshift.io/repositories/13692" target="_blank">
    <img src="https://trendshift.io/api/badge/repositories/13692" alt="snailyp%2Fgemini-balance | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/>
  </a>
</p>

> ⚠️ 本專案採用 CC BY-NC 4.0（署名-非商業性使用）授權條款。禁止任何形式的商業轉售服務。詳見 LICENSE 檔案。

> 原作者聲明：我從未在任何平台販售此服務。如果你遇到有人販售此服務，他們絕對是轉售者。請小心不要被騙。

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green.svg)](https://fastapi.tiangolo.com/)
[![Uvicorn](https://img.shields.io/badge/Uvicorn-running-purple.svg)](https://www.uvicorn.org/)
[![Telegram Group](https://img.shields.io/badge/Telegram-Group-blue.svg?logo=telegram)](https://t.me/+soaHax5lyI0wZDVl)

> Telegram 群組：<https://t.me/+soaHax5lyI0wZDVl>

## 專案介紹

Gemini Balance 是一個使用 Python FastAPI 建構的應用程式，旨在為 Google Gemini API 提供代理和負載平衡功能。它允許你管理多個 Gemini API Keys，並透過簡單的設定實現金鑰輪換、認證、模型篩選和狀態監控。此外，專案整合了圖片生成和多種圖床上傳功能，並支援以 OpenAI API 格式進行代理。

**專案結構：**

```plaintext
app/
├── config/       # 組態管理
├── core/         # 核心應用程式邏輯（FastAPI 實例建立、中介軟體等）
├── database/     # 資料庫模型和連線
├── domain/       # 商業領域物件（選用）
├── exception/    # 自訂例外
├── handler/      # 請求處理器（選用，或在 router 中處理）
├── log/          # 日誌設定
├── main.py       # 應用程式進入點
├── middleware/   # FastAPI 中介軟體
├── router/       # API 路由（Gemini、OpenAI、狀態頁面等）
├── scheduler/    # 排程任務（例如：Key 狀態檢查）
├── service/      # 商業邏輯服務（聊天、Key 管理、統計等）
├── static/       # 靜態檔案（CSS、JS）
├── templates/    # HTML 範本（例如：Key 狀態頁面）
├── utils/        # 工具函式
```

## ✨ 功能亮點

* **多 Key 負載平衡**：支援設定多個 Gemini API Keys（`API_KEYS`），自動依序輪詢，提高可用性和並發能力。
* **視覺化設定即時生效**：透過管理後台修改的設定無需重新啟動服務即可生效。記得點選儲存以套用變更。
    ![設定面板](files/image4.png)
* **雙協定 API 相容性**：支援以 Gemini 和 OpenAI 格式轉發 CHAT API 請求。

    ```plaintext
    openai baseurl `http://localhost:8000(/hf)/v1`
    gemini baseurl `http://localhost:8000(/gemini)/v1beta`
    ```

* **支援圖文聊天和圖片修改**：`IMAGE_MODELS` 設定哪些模型可以進行圖文聊天和圖片編輯。實際呼叫時，使用 `configured_model-image` 模型名稱來使用此功能。
    ![圖片生成聊天](files/image6.png)
    ![修改圖片](files/image7.png)
* **支援網路搜尋**：支援網路搜尋功能。`SEARCH_MODELS` 設定哪些模型可以進行網路搜尋。實際呼叫時，使用 `configured_model-search` 模型名稱來使用此功能。
    ![網路搜尋](files/image8.png)
* **Key 狀態監控**：提供 `/keys_status` 頁面（需要認證），即時檢視每個 Key 的狀態和使用情況。
    ![監控面板](files/image.png)
* **詳細日誌記錄**：提供詳細的錯誤日誌，方便排查問題。
    ![呼叫詳情](files/image1.png)
    ![日誌列表](files/image2.png)
    ![日誌詳情](files/image3.png)
* **支援自訂 Gemini 代理**：支援自訂 Gemini 代理，例如基於 Deno 或 Cloudflare 建構的代理。
* **OpenAI 圖片生成 API 相容性**：調整 `imagen-3.0-generate-002` 模型介面，使其相容於 OpenAI 圖片生成 API，支援用戶端呼叫。
* **彈性的 Key 新增方式**：使用正規表示式匹配 `gemini_key` 的彈性方式新增金鑰，並進行金鑰去重。
    ![新增 Key](files/image5.png)
* **OpenAI 格式 Embeddings API 相容性**：完美適配 OpenAI 格式的 `embeddings` 介面，可用於本機文件向量化。
* **串流回應最佳化**：可選的串流輸出最佳化器（`STREAM_OPTIMIZER_ENABLED`），改善長文本串流回應的體驗。
* **故障重試和 Key 管理**：自動處理 API 請求失敗，重試（`MAX_RETRIES`），失敗次數過多後自動停用 Key（`MAX_FAILURES`），並定期檢查恢復（`CHECK_INTERVAL_HOURS`）。
* **Docker 支援**：支援 AMD 和 ARM 架構的 Docker 部署。你也可以自行建構 Docker 映像。
    > 映像位址：docker pull ghcr.io/snailyp/gemini-balance:latest
* **自動模型列表維護**：支援獲取 OpenAI 和 Gemini 模型列表，完美相容 NewAPI 的自動模型列表獲取，無需手動輸入。
* **支援移除不使用的模型**：預設提供的模型太多，很多用不上，可以透過 `FILTERED_MODELS` 過濾掉。
* **代理支援**：支援設定 HTTP/SOCKS5 代理伺服器（`PROXIES`），用於存取 Gemini API，方便在特殊網路環境下使用。支援批次新增代理。
* **最佳化思考設定處理**：智慧處理思考設定 - 當 thinkingBudget 設為 0 時，會完全省略 thinkingConfig 以提高相容性。非思考模型會自動跳過思考設定。

## 📖 文件

* **[反向代理設定指南](gemini-balance-reverse-proxy-guide.md)** - 了解如何設定本機反向代理，讓應用程式以為在連接 Google Gemini API，但實際上請求會被轉發到 Gemini Balance 服務

## 🚀 快速開始

### 自行建構 Docker（推薦）

#### a) 使用 Dockerfile 建構

1. **建構映像**：

    ```bash
    docker build -t gemini-balance .
    ```

2. **執行容器**：

    ```bash
    docker run -d -p 8000:8000 --env-file .env gemini-balance
    ```

    * `-d`：在背景執行。
    * `-p 8000:8000`：將容器的 8000 連接埠對應到主機的 8000 連接埠。
    * `--env-file .env`：使用 `.env` 檔案設定環境變數。

    > 注意：如果使用 SQLite 資料庫，需要掛載資料卷以持久化
>
    > ```bash
    > docker run -d -p 8000:8000 --env-file .env -v /path/to/data:/app/data gemini-balance
    > ```
>
    > 其中 `/path/to/data` 是主機上的資料儲存路徑，`/app/data` 是容器內的資料目錄。

#### b) 使用現有的 Docker 映像部署

1. **拉取映像**：

    ```bash
    docker pull ghcr.io/snailyp/gemini-balance:latest
    ```

2. **執行容器**：

    ```bash
    docker run -d -p 8000:8000 --env-file .env ghcr.io/snailyp/gemini-balance:latest
    ```

    * `-d`：在背景執行。
    * `-p 8000:8000`：將容器的 8000 連接埠對應到主機的 8000 連接埠（根據需要調整）。
    * `--env-file .env`：使用 `.env` 檔案設定環境變數（確保執行命令的目錄中存在 `.env` 檔案）。

    > 注意：如果使用 SQLite 資料庫，需要掛載資料卷以持久化
>
    > ```bash
    > docker run -d -p 8000:8000 --env-file .env -v /path/to/data:/app/data ghcr.io/snailyp/gemini-balance:latest
    > ```
>
    > 其中 `/path/to/data` 是主機上的資料儲存路徑，`/app/data` 是容器內的資料目錄。

### 本機執行（適合開發和測試）

如果你想直接在本機執行原始碼進行開發或測試，請按照以下步驟操作：

1. **確保滿足前置條件**：
    * 將儲存庫複製到本機。
    * 安裝 Python 3.9 或更高版本。
    * 在專案根目錄建立並設定 `.env` 檔案（參考上面的「設定環境變數」部分）。
    * 安裝專案依賴：

        ```bash
        pip install -r requirements.txt
        ```

2. **啟動應用程式**：
    在專案根目錄執行以下命令：

    ```bash
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ```

    * `app.main:app`：指定 FastAPI 應用程式實例的位置（`app` 模組內 `main.py` 檔案中的 `app` 物件）。
    * `--host 0.0.0.0`：使應用程式可以從本機網路上的任何 IP 位址存取。
    * `--port 8000`：指定應用程式監聽的連接埠號（你可以根據需要更改）。
    * `--reload`：啟用自動重新載入。當你修改程式碼時，服務會自動重新啟動，非常適合開發環境（在生產環境中移除此選項）。

3. **存取應用程式**：
    應用程式啟動後，你可以透過瀏覽器或 API 工具存取 `http://localhost:8000`（或你指定的主機和連接埠）。

### 完整設定列表

| 設定項目                       | 說明                                                                        | 預設值                                                                                                                                                                                                                                   |
| :----------------------------- | :-------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **資料庫設定**                 |                                                                             |                                                                                                                                                                                                                                          |
| `DATABASE_TYPE`                | 選用，資料庫類型，支援 `mysql` 或 `sqlite`                                 | `mysql`                                                                                                                                                                                                                                  |
| `SQLITE_DATABASE`              | 選用，使用 `sqlite` 時必需，SQLite 資料庫檔案路徑                          | `default_db`                                                                                                                                                                                                                             |
| `MYSQL_HOST`                   | 使用 `mysql` 時必需，MySQL 資料庫主機位址                                  | `localhost`                                                                                                                                                                                                                              |
| `MYSQL_SOCKET`                 | 選用，MySQL 資料庫 socket 位址                                             | `/var/run/mysqld/mysqld.sock`                                                                                                                                                                                                            |
| `MYSQL_PORT`                   | 使用 `mysql` 時必需，MySQL 資料庫連接埠                                    | `3306`                                                                                                                                                                                                                                   |
| `MYSQL_USER`                   | 使用 `mysql` 時必需，MySQL 資料庫使用者名稱                                | `your_db_user`                                                                                                                                                                                                                           |
| `MYSQL_PASSWORD`               | 使用 `mysql` 時必需，MySQL 資料庫密碼                                      | `your_db_password`                                                                                                                                                                                                                       |
| `MYSQL_DATABASE`               | 使用 `mysql` 時必需，MySQL 資料庫名稱                                      | `defaultdb`                                                                                                                                                                                                                              |
| **API 相關設定**               |                                                                             |                                                                                                                                                                                                                                          |
| `API_KEYS`                     | 必需，用於負載平衡的 Gemini API 金鑰列表                                   | `["your-gemini-api-key-1", "your-gemini-api-key-2"]`                                                                                                                                                                                     |
| `ALLOWED_TOKENS`               | 必需，允許存取的權杖列表                                                   | `["your-access-token-1", "your-access-token-2"]`                                                                                                                                                                                         |
| `AUTH_TOKEN`                   | 選用，擁有所有權限的超級管理員權杖，未設定時預設為 `ALLOWED_TOKENS` 的第一個 | `sk-123456`                                                                                                                                                                                                              |
| `TEST_MODEL`                   | 選用，用於測試金鑰是否可用的模型名稱                                       | `gemini-1.5-flash`                                                                                                                                                                                                                       |
| `IMAGE_MODELS`                 | 選用，支援繪圖功能的模型列表                                               | `["gemini-2.0-flash-exp"]`                                                                                                                                                                                                               |
| `SEARCH_MODELS`                | 選用，支援搜尋功能的模型列表                                               | `["gemini-2.0-flash-exp"]`                                                                                                                                                                                                               |
| `FILTERED_MODELS`              | 選用，停用的模型列表                                                       | `["gemini-1.0-pro-vision-latest", ...]`                                                                                                                                                                                                  |
| `TOOLS_CODE_EXECUTION_ENABLED` | 選用，是否啟用程式碼執行工具                                               | `false`                                                                                                                                                                                                                                  |
| `SHOW_SEARCH_LINK`             | 選用，是否在回應中顯示搜尋結果連結                                         | `true`                                                                                                                                                                                                                                   |
| `SHOW_THINKING_PROCESS`        | 選用，是否顯示模型的思考過程                                               | `true`                                                                                                                                                                                                                                   |
| `THINKING_MODELS`              | 選用，支援思考功能的模型列表                                               | `[]`                                                                                                                                                                                                                                     |
| `THINKING_BUDGET_MAP`          | 選用，思考功能預算對應（model_name:budget_value）。當預算為 0 時，會完全省略 thinkingConfig | `{}`                                                                                                                                                                                                                                     |
| `URL_NORMALIZATION_ENABLED`    | 選用，是否啟用智慧 URL 路由對應                                            | `false`                                                                                                                                                                                                                                  |
| `BASE_URL`                     | 選用，Gemini API 基礎 URL，預設不需修改                                    | `https://generativelanguage.googleapis.com/v1beta`                                                                                                                                                                                       |
| `MAX_FAILURES`                 | 選用，單一金鑰允許失敗的次數                                               | `3`                                                                                                                                                                                                                                      |
| `MAX_RETRIES`                  | 選用，失敗 API 請求的最大重試次數                                          | `3`                                                                                                                                                                                                                                      |
| `CHECK_INTERVAL_HOURS`         | 選用，檢查停用的 Key 是否恢復的時間間隔（小時）                            | `1`                                                                                                                                                                                                                                      |
| `TIMEZONE`                     | 選用，應用程式使用的時區                                                   | `Asia/Shanghai`                                                                                                                                                                                                                          |
| `TIME_OUT`                     | 選用，請求逾時（秒）                                                       | `300`                                                                                                                                                                                                                                    |
| `PROXIES`                      | 選用，代理伺服器列表（例如：`http://user:pass@host:port`、`socks5://host:port`） | `[]`                                                                                                                                                                                                                                     |
| `LOG_LEVEL`                    | 選用，日誌等級，例如：DEBUG、INFO、WARNING、ERROR、CRITICAL               | `INFO`                                                                                                                                                                                                                                   |
| `AUTO_DELETE_ERROR_LOGS_ENABLED` | 選用，是否啟用自動刪除錯誤日誌                                           | `true`                                                                                                                                                                                                                                   |
| `AUTO_DELETE_ERROR_LOGS_DAYS`  | 選用，自動刪除超過此天數的錯誤日誌（例如：1、7、30）                      | `7`                                                                                                                                                                                                                                      |
| `AUTO_DELETE_REQUEST_LOGS_ENABLED`| 選用，是否啟用自動刪除請求日誌                                           | `false`                                                                                                                                                                                                                                  |
| `AUTO_DELETE_REQUEST_LOGS_DAYS` | 選用，自動刪除超過此天數的請求日誌（例如：1、7、30）                      | `30`                                                                                                                                                                                                                                     |
| `SAFETY_SETTINGS`              | 選用，安全設定（JSON 字串格式），用於設定內容安全閾值。範例值可能需要根據實際模型支援進行調整。 | `[{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "OFF"}, {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "OFF"}, {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "OFF"}, {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "OFF"}, {"category": "HARM_CATEGORY_CIVIC_INTEGRITY", "threshold": "BLOCK_NONE"}]` |
| **TTS 相關**                   |                                                                             |                                                                                                                                                                                                                                          |
| `TTS_MODEL`                    | 選用，TTS 模型名稱                                                         | `gemini-2.5-flash-preview-tts`                                                                                                                                                                                                           |
| `TTS_VOICE_NAME`               | 選用，TTS 語音名稱                                                         | `Zephyr`                                                                                                                                                                                                                                 |
| `TTS_SPEED`                    | 選用，TTS 速度                                                             | `normal`                                                                                                                                                                                                                                 |
| **圖片生成相關**               |                                                                             |                                                                                                                                                                                                                                          |
| `PAID_KEY`                     | 選用，付費 API Key，用於進階功能如圖片生成                                 | `your-paid-api-key`                                                                                                                                                                                                                        |
| `CREATE_IMAGE_MODEL`           | 選用，圖片生成模型                                                         | `imagen-3.0-generate-002`                                                                                                                                                                                                                  |
| `UPLOAD_PROVIDER`              | 選用，圖片上傳提供者：`smms`、`picgo`、`cloudflare_imgbed`                 | `smms`                                                                                                                                                                                                                                   |
| `SMMS_SECRET_TOKEN`            | 選用，SM.MS 圖床的 API Token                                               | `your-smms-token`                                                                                                                                                                                                                          |
| `PICGO_API_KEY`                | 選用，[PicoGo](https://www.picgo.net/) 圖床的 API Key                      | `your-picogo-apikey`                                                                                                                                                                                                                         |
| `CLOUDFLARE_IMGBED_URL`        | 選用，[CloudFlare](https://github.com/MarSeventh/CloudFlare-ImgBed) 圖床上傳位址 | `https://xxxxxxx.pages.dev/upload`                                                                                                                                                                                           |
| `CLOUDFLARE_IMGBED_AUTH_CODE`  | 選用，CloudFlare 圖床的認證金鑰                                            | `your-cloudflare-imgber-auth-code`                                                                                                                                                                                                           |
| **串流最佳化相關**             |                                                                             |                                                                                                                                                                                                                                          |
| `STREAM_OPTIMIZER_ENABLED`     | 選用，是否啟用串流輸出最佳化                                               | `false`                                                                                                                                                                                                                                  |
| `STREAM_MIN_DELAY`             | 選用，串流輸出最小延遲                                                     | `0.016`                                                                                                                                                                                                                                  |
| `STREAM_MAX_DELAY`             | 選用，串流輸出最大延遲                                                     | `0.024`                                                                                                                                                                                                                                  |
| `STREAM_SHORT_TEXT_THRESHOLD`  | 選用，短文本閾值                                                           | `10`                                                                                                                                                                                                                                     |
| `STREAM_LONG_TEXT_THRESHOLD`   | 選用，長文本閾值                                                           | `50`                                                                                                                                                                                                                                     |
| `STREAM_CHUNK_SIZE`            | 選用，串流輸出區塊大小                                                     | `5`                                                                                                                                                                                                                                      |
| **假串流相關**                 |                                                                             |                                                                                                                                                                                                                                          |
| `FAKE_STREAM_ENABLED`          | 選用，是否啟用假串流，用於不支援串流的模型或場景                           | `false`                                                                                                                                                                                                                                  |
| `FAKE_STREAM_EMPTY_DATA_INTERVAL_SECONDS` | 選用，假串流期間發送心跳空資料的間隔（秒）                       | `5`                                                                                                                                                                                                                                      |

## ⚙️ API 端點

以下是服務提供的主要 API 端點：

### Gemini API 相關（`(/gemini)/v1beta`）

* `GET /models`：列出可用的 Gemini 模型。
* `POST /models/{model_name}:generateContent`：使用指定的 Gemini 模型生成內容。
* `POST /models/{model_name}:streamGenerateContent`：使用指定的 Gemini 模型串流生成內容。
* `POST /models/{model_name}:countTokens`：使用 Gemini 模型計算指定輸入的權杖數。

### OpenAI API 相關

* `GET (/hf)/v1/models`：列出可用的模型（底層使用 Gemini 格式）。
* `POST (/hf)/v1/chat/completions`：執行聊天完成（底層使用 Gemini 格式，支援串流）。
* `POST (/hf)/v1/embeddings`：建立文字嵌入（底層使用 Gemini 格式）。
* `POST (/hf)/v1/images/generations`：生成圖片（底層使用 Gemini 格式）。
* `GET /openai/v1/models`：列出可用的模型（底層使用 OpenAI 格式）。
* `POST /openai/v1/chat/completions`：執行聊天完成（底層使用 OpenAI 格式，支援串流，可防止截斷，速度更快）。
* `POST /openai/v1/embeddings`：建立文字嵌入（底層使用 OpenAI 格式）。
* `POST /openai/v1/images/generations`：生成圖片（底層使用 OpenAI 格式）。

## 🤝 貢獻

歡迎提交 Pull Request 或 Issue。

## 🎉 特別感謝

特別感謝以下專案和平台為本專案提供圖床服務：

* [PicGo](https://www.picgo.net/)
* [SM.MS](https://smms.app/)
* [CloudFlare-ImgBed](https://github.com/MarSeventh/CloudFlare-ImgBed) 開源專案

## 🙏 感謝貢獻者

感謝所有為此專案做出貢獻的開發者！

[![Contributors](https://contrib.rocks/image?repo=snailyp/gemini-balance)](https://github.com/snailyp/gemini-balance/graphs/contributors)

## 感謝我們的支援者

特別感謝 DigitalOcean 提供穩定可靠的雲端基礎設施，讓這個專案持續運作！
[![DigitalOcean Logo](files/dataocean.svg)](https://m.do.co/c/b249dd7f3b4c)

本專案的 CDN 加速和安全防護由騰訊 EdgeOne 贊助。
[![EdgeOne Logo](https://edgeone.ai/media/34fe3a45-492d-4ea4-ae5d-ea1087ca7b4b.png)](https://edgeone.ai/?from=github)

## ⭐ Star 歷史

[![Star History Chart](https://api.star-history.com/svg?repos=snailyp/gemini-balance&type=Date)](https://star-history.com/#snailyp/gemini-balance&Date)

## 💖 友善專案

* **[OneLine](https://github.com/chengtx809/OneLine)** by [chengtx809](https://github.com/chengtx809) - OneLine：AI 驅動的熱門事件時間軸生成工具

## 🎁 專案支援

如果你覺得這個專案對你有幫助，可以考慮透過 [愛發電](https://afdian.com/a/snaily) 支援我。

## 授權條款

本專案採用 CC BY-NC 4.0（署名-非商業性使用）授權條款。禁止任何形式的商業轉售服務。詳見 LICENSE 檔案。