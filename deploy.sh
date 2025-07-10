#!/bin/bash
# Gemini Balance 部署管理腳本 - 互動式選單版本
# 支援多種部署模式：重建、開發、快速重啟、首次啟動等

set -e

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# 預設值
MODE=""
COMPOSE_FILE=""  # 將由智能檢測決定
DEFAULT_PORT=""  # 將從 compose 檔案提取
CONTAINER_NAME="gemini-balance"
INTERACTIVE=true

# 智能檢測函數
# 自動檢測可用的 Docker Compose 檔案
detect_compose_files() {
    local files=()
    for f in docker-compose*.yml docker-compose*.yaml; do
        [ -f "$f" ] && files+=("$f")
    done
    echo "${files[@]}"
}

# 從 Docker Compose 檔案提取端口
extract_port_from_compose() {
    local compose_file="$1"
    # 查找映射到容器 8000 端口的主機端口
    local port=$(grep -E '^\s*-\s*["\047]?[0-9]+:8000["\047]?' "$compose_file" 2>/dev/null | 
                 sed -E 's/^[^0-9]*([0-9]+):8000.*/\1/' | head -1)
    
    # 如果找不到，查找 ports 區段下的第一個端口
    if [ -z "$port" ]; then
        port=$(awk '/ports:/{flag=1; next} flag && /^\s*-/{print; exit}' "$compose_file" 2>/dev/null |
               sed -E 's/^[^0-9]*([0-9]+):[0-9]+.*/\1/')
    fi
    
    # 如果還是找不到，使用預設值
    echo "${port:-8000}"
}

# 自動選擇最合適的 compose 檔案
auto_select_compose_file() {
    local files=($(detect_compose_files))
    
    if [ ${#files[@]} -eq 0 ]; then
        echo -e "${RED}❌ 找不到任何 Docker Compose 檔案${NC}"
        exit 1
    elif [ ${#files[@]} -eq 1 ]; then
        echo "${files[0]}"
    else
        # 優先順序：docker-compose.reverse-proxy.yml > docker-compose.yml > 其他
        for priority in "docker-compose.reverse-proxy.yml" "docker-compose.yml"; do
            for f in "${files[@]}"; do
                if [ "$f" = "$priority" ]; then
                    echo "$f"
                    return
                fi
            done
        done
        # 如果沒有優先檔案，返回第一個
        echo "${files[0]}"
    fi
}

# 顯示使用說明
usage() {
    echo -e "${CYAN}Gemini Balance 部署管理腳本${NC}"
    echo ""
    echo "使用方法: $0 [選項] [命令]"
    echo ""
    echo "命令:"
    echo "  start         🚀 首次啟動服務"
    echo "  stop          🛑 停止服務"
    echo "  restart       ⚡ 快速重啟（不重建）"
    echo "  rebuild       🔨 重新構建並部署"
    echo "  dev           🔧 開發模式（自動重載）"
    echo "  logs          📋 查看日誌"
    echo "  status        📊 查看狀態"
    echo ""
    echo "選項:"
    echo "  -f, --file <file>     指定 Docker Compose 文件"
    echo "  -p, --port <port>     指定服務端口"
    echo "  -h, --help            顯示此幫助訊息"
    echo ""
    echo "範例:"
    echo "  $0                    # 互動式選單"
    echo "  $0 start              # 直接啟動服務"
    echo "  $0 dev                # 啟動開發模式"
    echo "  $0 logs               # 查看日誌"
    echo "  $0 -f docker-compose.reverse-proxy.yml start  # 使用指定檔案"
    exit 1
}

# 解析參數
while [[ $# -gt 0 ]]; do
    case $1 in
        -m|--mode)
            MODE="$2"
            INTERACTIVE=false
            shift 2
            ;;
        -f|--file)
            COMPOSE_FILE="$2"
            shift 2
            ;;
        -p|--port)
            DEFAULT_PORT="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        # 直接命令模式
        start|stop|restart|rebuild|dev|logs|status)
            MODE="$1"
            INTERACTIVE=false
            shift
            ;;
        *)
            echo -e "${RED}未知選項或命令: $1${NC}"
            usage
            ;;
    esac
done

# 檢查 Docker 是否運行
check_docker() {
    if ! docker info >/dev/null 2>&1; then
        echo -e "${RED}❌ Docker 未運行或未安裝${NC}"
        echo -e "${YELLOW}請先啟動 Docker Desktop 或 Docker 服務${NC}"
        exit 1
    fi
}

# 初始化配置（在參數解析後調用）
initialize_config() {
    # 如果沒有指定 compose 檔案，自動選擇
    if [ -z "$COMPOSE_FILE" ]; then
        COMPOSE_FILE=$(auto_select_compose_file)
        echo -e "${BLUE}🔍 自動選擇 Docker Compose 檔案: ${GREEN}$COMPOSE_FILE${NC}"
    fi
    
    # 如果沒有指定端口，從 compose 檔案提取
    if [ -z "$DEFAULT_PORT" ]; then
        DEFAULT_PORT=$(extract_port_from_compose "$COMPOSE_FILE")
        echo -e "${BLUE}🔍 從 $COMPOSE_FILE 提取端口: ${GREEN}$DEFAULT_PORT${NC}"
    fi
}

# 檢查必要文件
check_requirements() {
    if [ ! -f ".env" ]; then
        echo -e "${RED}❌ 找不到 .env 文件${NC}"
        echo -e "${YELLOW}正在從 .env.example 創建 .env 文件...${NC}"
        if [ -f ".env.example" ]; then
            cp .env.example .env
            echo -e "${GREEN}✅ 已創建 .env 文件，請編輯配置後重新運行${NC}"
            exit 0
        else
            echo -e "${RED}❌ 找不到 .env.example 文件${NC}"
            exit 1
        fi
    fi
    
    if [ ! -f "$COMPOSE_FILE" ]; then
        echo -e "${RED}❌ 找不到 Docker Compose 文件: $COMPOSE_FILE${NC}"
        exit 1
    fi
}

# 清屏函數
clear_screen() {
    clear
}

# 顯示標題橫幅
show_banner() {
    clear_screen
    echo -e "${CYAN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                                                        ║${NC}"
    echo -e "${CYAN}║${BOLD}        Gemini Balance 部署管理工具 v3.0${NC}${CYAN}              ║${NC}"
    echo -e "${CYAN}║                                                        ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# 獲取容器狀態
get_container_status() {
    if docker ps | grep -q $CONTAINER_NAME; then
        if curl -s http://localhost:$DEFAULT_PORT/health > /dev/null 2>&1; then
            echo "running_healthy"
        else
            echo "running_unhealthy"
        fi
    else
        echo "stopped"
    fi
}

# 顯示當前狀態
show_current_status() {
    local status=$(get_container_status)
    echo -e "${BLUE}當前狀態：${NC}"
    case $status in
        "running_healthy")
            echo -e "  ${GREEN}● 服務運行中（健康）${NC}"
            echo -e "  ${GRAY}地址: http://localhost:$DEFAULT_PORT${NC}"
            ;;
        "running_unhealthy")
            echo -e "  ${YELLOW}● 服務運行中（不健康）${NC}"
            ;;
        "stopped")
            echo -e "  ${RED}● 服務已停止${NC}"
            ;;
    esac
    echo ""
}

# 顯示選單
show_menu() {
    show_banner
    show_current_status
    
    echo -e "${BOLD}請選擇操作：${NC}"
    echo ""
    echo -e "  ${CYAN}[1]${NC} 🚀 ${BOLD}啟動服務${NC} - 檢查環境並啟動"
    echo -e "  ${CYAN}[2]${NC} ⚡ ${BOLD}快速重啟${NC} - 重啟容器"
    echo -e "  ${CYAN}[3]${NC} 🔨 ${BOLD}重建部署${NC} - 重新構建並部署"
    echo -e "  ${CYAN}[4]${NC} 🔧 ${BOLD}開發模式${NC} - 掛載代碼，自動重載"
    echo ""
    echo -e "  ${CYAN}[5]${NC} 📋 ${BOLD}查看日誌${NC} - 實時查看日誌"
    echo -e "  ${CYAN}[6]${NC} 📊 ${BOLD}服務狀態${NC} - 查看狀態信息"
    echo -e "  ${CYAN}[7]${NC} 🛑 ${BOLD}停止服務${NC} - 停止容器"
    echo ""
    echo -e "  ${CYAN}[8]${NC} ⚙️  ${BOLD}高級選項${NC} - 更多選項"
    echo -e "  ${CYAN}[0]${NC} 🚪 ${BOLD}退出${NC}"
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -ne "${BOLD}請輸入選項 [0-8]: ${NC}"
}

# 高級選項選單
show_advanced_menu() {
    clear_screen
    show_banner
    
    echo -e "${BOLD}高級選項：${NC}"
    echo ""
    echo -e "  ${CYAN}[1]${NC} 🗑️  ${BOLD}清理映像${NC} - 刪除未使用的 Docker 映像"
    echo -e "  ${CYAN}[2]${NC} 📦 ${BOLD}備份數據${NC} - 備份 data 目錄"
    echo -e "  ${CYAN}[3]${NC} 🔄 ${BOLD}更新代碼${NC} - 從 Git 拉取最新代碼"
    echo -e "  ${CYAN}[4]${NC} 🐚 ${BOLD}進入容器${NC} - 進入容器 Shell"
    echo -e "  ${CYAN}[5]${NC} 📈 ${BOLD}資源監控${NC} - 查看容器資源使用"
    echo -e "  ${CYAN}[6]${NC} 🌐 ${BOLD}代理管理${NC} - WSL nginx 代理控制"
    echo ""
    echo -e "  ${CYAN}[0]${NC} ↩️  ${BOLD}返回主選單${NC}"
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -ne "${BOLD}請輸入選項 [0-6]: ${NC}"
}

# 等待用戶按鍵
wait_for_key() {
    echo ""
    echo -ne "${GRAY}按任意鍵返回選單...${NC}"
    read -n 1 -s
}

# 代理管理選單
show_proxy_menu() {
    while true; do
        clear_screen
        show_banner
        
        echo -e "${BOLD}🌐 代理管理：${NC}"
        echo ""
        
        # 檢查代理狀態
        check_proxy_status
        
        echo ""
        echo -e "  ${CYAN}[1]${NC} 🟢 ${BOLD}啟用代理${NC} - 啟用 WSL nginx 代理"
        echo -e "  ${CYAN}[2]${NC} 🔴 ${BOLD}停用代理${NC} - 停用 WSL nginx 代理"
        echo -e "  ${CYAN}[3]${NC} 📊 ${BOLD}代理狀態${NC} - 查看完整代理狀態"
        echo -e "  ${CYAN}[4]${NC} 🧪 ${BOLD}測試代理${NC} - 測試代理功能"
        echo -e "  ${CYAN}[5]${NC} 🔄 ${BOLD}重啟 nginx${NC} - 重啟 WSL nginx 服務"
        echo ""
        echo -e "  ${CYAN}[0]${NC} ↩️  ${BOLD}返回高級選單${NC}"
        echo ""
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -ne "${BOLD}請輸入選項 [0-5]: ${NC}"
        
        read proxy_choice
        case $proxy_choice in
            1)
                enable_proxy
                wait_for_key
                ;;
            2)
                disable_proxy
                wait_for_key
                ;;
            3)
                show_detailed_proxy_status
                wait_for_key
                ;;
            4)
                test_proxy
                wait_for_key
                ;;
            5)
                restart_nginx
                wait_for_key
                ;;
            0)
                break
                ;;
            *)
                echo -e "${RED}無效選項${NC}"
                sleep 1
                ;;
        esac
    done
}

# 檢查代理狀態
check_proxy_status() {
    local nginx_status=$(systemctl is-active nginx 2>/dev/null || echo "inactive")
    local hosts_status="停用"
    
    if grep -q "^127.0.0.1 generativelanguage.googleapis.com" /etc/hosts 2>/dev/null; then
        hosts_status="啟用"
    fi
    
    echo -e "${BOLD}當前狀態：${NC}"
    if [ "$nginx_status" = "active" ]; then
        echo -e "  WSL nginx: ${GREEN}運行中${NC}"
    else
        echo -e "  WSL nginx: ${RED}已停止${NC}"
    fi
    
    if [ "$hosts_status" = "啟用" ]; then
        echo -e "  WSL hosts: ${GREEN}已啟用${NC}"
    else
        echo -e "  WSL hosts: ${YELLOW}已停用${NC}"
    fi
}

# 啟用代理
enable_proxy() {
    clear_screen
    echo -e "${YELLOW}🟢 啟用 WSL nginx 代理...${NC}"
    
    # 啟動 nginx 服務
    if ! systemctl is-active --quiet nginx; then
        echo -e "${BLUE}啟動 nginx 服務...${NC}"
        sudo systemctl start nginx
    fi
    
    # 啟用 hosts 檔案設定
    if [ -f "local-proxy-management/scripts/proxy-control.sh" ]; then
        echo -e "${BLUE}啟用 hosts 檔案代理設定...${NC}"
        bash local-proxy-management/scripts/proxy-control.sh
    else
        echo -e "${BLUE}手動啟用 hosts 檔案設定...${NC}"
        if ! grep -q "^127.0.0.1 generativelanguage.googleapis.com" /etc/hosts; then
            echo "127.0.0.1 generativelanguage.googleapis.com" | sudo tee -a /etc/hosts > /dev/null
            echo -e "${GREEN}✅ hosts 檔案已更新${NC}"
        else
            echo -e "${GREEN}✅ hosts 檔案已經配置${NC}"
        fi
    fi
    
    echo -e "${GREEN}✅ 代理已啟用${NC}"
}

# 停用代理
disable_proxy() {
    clear_screen
    echo -e "${YELLOW}🔴 停用 WSL nginx 代理...${NC}"
    
    # 停用 hosts 檔案設定
    if [ -f "local-proxy-management/scripts/proxy-control.sh" ]; then
        echo -e "${BLUE}停用 hosts 檔案代理設定...${NC}"
        bash local-proxy-management/scripts/proxy-control.sh
    else
        echo -e "${BLUE}手動停用 hosts 檔案設定...${NC}"
        sudo sed -i 's/^127.0.0.1 generativelanguage.googleapis.com/# 127.0.0.1 generativelanguage.googleapis.com/' /etc/hosts
        echo -e "${GREEN}✅ hosts 檔案已更新${NC}"
    fi
    
    echo -e "${GREEN}✅ 代理已停用${NC}"
    echo -e "${CYAN}ℹ️  nginx 服務保持運行，僅停用 hosts 代理設定${NC}"
}

# 顯示詳細代理狀態
show_detailed_proxy_status() {
    clear_screen
    echo -e "${BOLD}📊 詳細代理狀態：${NC}"
    echo ""
    
    # nginx 服務狀態
    echo -e "${CYAN}🔧 WSL nginx 服務：${NC}"
    sudo systemctl status nginx --no-pager -l
    echo ""
    
    # 端口監聽狀態
    echo -e "${CYAN}🌐 端口監聽：${NC}"
    ss -tlnp | grep :443 || echo "  443 端口未監聽"
    echo ""
    
    # hosts 檔案狀態
    echo -e "${CYAN}📝 hosts 檔案：${NC}"
    grep "generativelanguage.googleapis.com" /etc/hosts || echo "  無相關設定"
    echo ""
    
    # 容器狀態
    echo -e "${CYAN}🐳 Gemini Balance 容器：${NC}"
    docker ps | grep gemini-balance || echo "  容器未運行"
}

# 測試代理
test_proxy() {
    clear_screen
    echo -e "${YELLOW}🧪 測試代理功能...${NC}"
    echo ""
    
    # 測試 nginx 響應
    echo -e "${BLUE}測試 nginx 響應...${NC}"
    if curl -s -k https://localhost:443/ > /dev/null; then
        echo -e "  ${GREEN}✅ nginx HTTPS 響應正常${NC}"
    else
        echo -e "  ${RED}❌ nginx HTTPS 響應失敗${NC}"
    fi
    
    # 測試 gemini-balance 服務
    echo -e "${BLUE}測試 gemini-balance 服務...${NC}"
    if curl -s http://localhost:$DEFAULT_PORT/health > /dev/null; then
        echo -e "  ${GREEN}✅ gemini-balance 服務正常${NC}"
    else
        echo -e "  ${RED}❌ gemini-balance 服務無響應${NC}"
    fi
    
    echo ""
    echo -e "${CYAN}ℹ️  更詳細的測試請參考 local-proxy-management/scripts/windows/ 中的測試腳本${NC}"
}

# 重啟 nginx
restart_nginx() {
    clear_screen
    echo -e "${YELLOW}🔄 重啟 WSL nginx 服務...${NC}"
    
    sudo systemctl restart nginx
    sleep 2
    
    if systemctl is-active --quiet nginx; then
        echo -e "${GREEN}✅ nginx 重啟成功${NC}"
    else
        echo -e "${RED}❌ nginx 重啟失敗${NC}"
        echo -e "${YELLOW}錯誤訊息：${NC}"
        sudo systemctl status nginx --no-pager
    fi
}

# 確認操作
confirm_action() {
    local message="$1"
    echo -ne "${YELLOW}$message (y/N): ${NC}"
    read -r response
    case "$response" in
        [yY][eE][sS]|[yY]) 
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# 如果是互動模式，顯示選單
if [ "$INTERACTIVE" = true ]; then
    # 檢查 Docker
    check_docker
    
    while true; do
        show_menu
        read -r choice
        
        case $choice in
            1) MODE="start" ;;
            2) MODE="restart" ;;
            3) MODE="rebuild" ;;
            4) MODE="dev" ;;
            5) MODE="logs" ;;
            6) MODE="status" ;;
            7) MODE="stop" ;;
            8) 
                while true; do
                    show_advanced_menu
                    read -r adv_choice
                    
                    case $adv_choice in
                        1)
                            clear_screen
                            echo -e "${YELLOW}🗑️  清理 Docker 映像...${NC}"
                            docker image prune -f
                            echo -e "${GREEN}✅ 清理完成${NC}"
                            wait_for_key
                            ;;
                        2)
                            clear_screen
                            echo -e "${YELLOW}📦 備份數據...${NC}"
                            backup_name="gemini-balance-backup-$(date +%Y%m%d_%H%M%S).tar.gz"
                            tar -czf "$backup_name" data/
                            echo -e "${GREEN}✅ 備份完成: $backup_name${NC}"
                            wait_for_key
                            ;;
                        3)
                            clear_screen
                            echo -e "${YELLOW}🔄 更新代碼...${NC}"
                            git pull
                            echo -e "${GREEN}✅ 代碼更新完成${NC}"
                            wait_for_key
                            ;;
                        4)
                            clear_screen
                            echo -e "${CYAN}進入容器 Shell...${NC}"
                            docker exec -it $CONTAINER_NAME bash
                            ;;
                        5)
                            clear_screen
                            echo -e "${CYAN}容器資源監控（按 Ctrl+C 退出）：${NC}"
                            docker stats $CONTAINER_NAME
                            ;;
                        6)
                            show_proxy_menu
                            ;;
                        0)
                            break
                            ;;
                        *)
                            echo -e "${RED}無效選項${NC}"
                            sleep 1
                            ;;
                    esac
                done
                continue
                ;;
            0)
                echo -e "${GREEN}再見！${NC}"
                exit 0
                ;;
            *)
                echo -e "${RED}無效選項，請重新選擇${NC}"
                sleep 1
                continue
                ;;
        esac
        
        # 如果選擇了操作，跳出選單循環
        if [ -n "$MODE" ]; then
            break
        fi
    done
    
    clear_screen
fi

# 執行前檢查
check_docker

# 初始化配置
initialize_config
if [ "$MODE" != "logs" ] && [ "$MODE" != "status" ] && [ "$MODE" != "stop" ]; then
    check_requirements
fi

# 健康檢查函數
health_check() {
    echo -e "${BLUE}🏥 檢查服務健康狀態...${NC}"
    local max_attempts=15
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:$DEFAULT_PORT/health > /dev/null; then
            echo -e "${GREEN}✅ 服務健康檢查通過！${NC}"
            return 0
        fi
        
        echo -ne "${YELLOW}⏳ 等待服務就緒... ($attempt/$max_attempts)\r${NC}"
        sleep 2
        ((attempt++))
    done
    
    echo -e "${RED}❌ 服務健康檢查失敗${NC}"
    echo -e "${YELLOW}請檢查日誌: docker logs $CONTAINER_NAME${NC}"
    return 1
}

# 顯示服務信息
show_service_info() {
    echo ""
    echo -e "${CYAN}╔════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║            服務信息                    ║${NC}"
    echo -e "${CYAN}╠════════════════════════════════════════╣${NC}"
    echo -e "${CYAN}║${NC} 本地地址: ${GREEN}http://localhost:$DEFAULT_PORT${NC}"
    echo -e "${CYAN}║${NC} 容器名稱: ${GREEN}$CONTAINER_NAME${NC}"
    echo -e "${CYAN}║${NC} Compose檔案: ${GREEN}$COMPOSE_FILE${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}📝 常用命令：${NC}"
    echo -e "  查看日誌:     ${YELLOW}$0 -m logs${NC}"
    echo -e "  查看狀態:     ${YELLOW}$0 -m status${NC}"
    echo -e "  停止服務:     ${YELLOW}$0 -m stop${NC}"
    echo -e "  開發模式:     ${YELLOW}$0 -m dev${NC}"
    echo ""
}

# 執行操作前顯示標題（非互動模式）
if [ "$INTERACTIVE" = false ]; then
    show_banner
fi

case $MODE in
    # 處理 restart 和 quick 的別名
    quick)
        MODE="restart"
        ;;&  # 繼續執行下一個 case
    restart)
        echo -e "${PURPLE}⚡ 快速重啟模式${NC}"
        echo ""
        docker compose -f $COMPOSE_FILE restart
        
        # 等待容器重啟
        sleep 3
        
        # 在容器內執行資料庫遷移（快速重啟也要檢查）
        if [ -f "migrations/migration_manager.py" ] && [ -f "data/gemini.db" ]; then
            # 靜默檢查，只有需要遷移時才顯示
            docker exec $CONTAINER_NAME python /app/migrations/migration_manager.py --quiet || {
                echo -e "${BLUE}🔄 發現新的資料庫遷移...${NC}"
                docker exec $CONTAINER_NAME python /app/migrations/migration_manager.py
            }
        fi
        
        if health_check; then
            show_service_info
        fi
        ;;
        
    start)
        echo -e "${PURPLE}🎯 首次啟動模式${NC}"
        echo ""
        
        # 創建必要目錄
        echo -e "${BLUE}📁 創建必要目錄...${NC}"
        mkdir -p data
        
        # 執行資料庫遷移（如果需要）
        if [ -f "migrations/migrate_sqlite.py" ]; then
            echo -e "${BLUE}🔄 檢查資料庫遷移...${NC}"
            # 如果資料庫存在，執行遷移
            if [ -f "data/gemini.db" ]; then
                python3 migrations/migrate_sqlite.py || echo -e "${YELLOW}⚠️  遷移腳本執行失敗（可能需要在容器內執行）${NC}"
            fi
        fi
        
        # 檢查映像是否存在
        if ! docker images | grep -q "^$CONTAINER_NAME "; then
            echo -e "${YELLOW}🔨 構建 Docker 映像...${NC}"
            docker build -t $CONTAINER_NAME .
        else
            echo -e "${GREEN}✅ Docker 映像已存在${NC}"
        fi
        
        # 停止現有容器
        if docker ps -a | grep -q $CONTAINER_NAME; then
            echo -e "${YELLOW}🛑 停止現有容器...${NC}"
            docker compose -f $COMPOSE_FILE down
        fi
        
        # 啟動服務
        echo -e "${YELLOW}🚀 啟動服務...${NC}"
        docker compose -f $COMPOSE_FILE up -d
        
        # 等待容器啟動
        echo -e "${GRAY}等待容器完全啟動...${NC}"
        sleep 5
        
        # 在容器內執行資料庫遷移
        if [ -f "migrations/migration_manager.py" ]; then
            if [ -f "data/gemini.db" ]; then
                echo -e "${BLUE}🔄 檢查資料庫遷移...${NC}"
                # 先檢查遷移腳本是否存在於容器中
                if docker exec $CONTAINER_NAME ls /app/migrations/migration_manager.py >/dev/null 2>&1; then
                    # 使用新的遷移管理器
                    docker exec $CONTAINER_NAME python /app/migrations/migration_manager.py --quiet || {
                        # 如果失敗，顯示詳細信息
                        echo -e "${YELLOW}⚠️  遷移需要執行，顯示詳細信息：${NC}"
                        docker exec $CONTAINER_NAME python /app/migrations/migration_manager.py
                    }
                else
                    echo -e "${RED}❌ 遷移腳本未找到於容器中，請重新構建映像${NC}"
                fi
            else
                echo -e "${YELLOW}📦 新安裝，尚無資料庫${NC}"
            fi
        fi
        
        # 健康檢查
        if health_check; then
            show_service_info
        fi
        ;;
        
    rebuild)
        echo -e "${PURPLE}🔨 重建部署模式${NC}"
        echo ""
        
        echo -e "${YELLOW}📦 構建新的 Docker 映像...${NC}"
        docker build -t $CONTAINER_NAME .
        
        echo ""
        echo -e "${YELLOW}🛑 停止並移除現有容器...${NC}"
        docker compose -f $COMPOSE_FILE down
        
        echo ""
        echo -e "${YELLOW}🚀 啟動新容器...${NC}"
        docker compose -f $COMPOSE_FILE up -d
        
        # 等待容器啟動
        echo -e "${GRAY}等待容器完全啟動...${NC}"
        sleep 5
        
        # 在容器內執行資料庫遷移
        if [ -f "migrations/migration_manager.py" ]; then
            if [ -f "data/gemini.db" ]; then
                echo -e "${BLUE}🔄 檢查資料庫遷移...${NC}"
                # 先檢查遷移腳本是否存在於容器中
                if docker exec $CONTAINER_NAME ls /app/migrations/migration_manager.py >/dev/null 2>&1; then
                    # 使用新的遷移管理器
                    docker exec $CONTAINER_NAME python /app/migrations/migration_manager.py --quiet || {
                        # 如果失敗，顯示詳細信息
                        echo -e "${YELLOW}⚠️  遷移需要執行，顯示詳細信息：${NC}"
                        docker exec $CONTAINER_NAME python /app/migrations/migration_manager.py
                    }
                else
                    echo -e "${RED}❌ 遷移腳本未找到於容器中，請重新構建映像${NC}"
                fi
            else
                echo -e "${YELLOW}📦 新安裝，尚無資料庫${NC}"
            fi
        fi
        
        if health_check; then
            show_service_info
        fi
        ;;
        
    dev)
        echo -e "${PURPLE}🔧 開發模式${NC}"
        echo ""
        
        # 創建臨時的 docker-compose override 文件
        cat > docker-compose.dev.yml << EOF
version: '3.8'
services:
  $CONTAINER_NAME:
    volumes:
      - ./app:/app/app:ro  # 掛載本地代碼（只讀）
      - ./data:/app/data
    environment:
      - PYTHONDONTWRITEBYTECODE=1  # 不生成 .pyc 文件
      - PYTHONUNBUFFERED=1          # 不緩衝輸出
    command: >
      sh -c "pip install watchdog &&
             watchmedo auto-restart -d /app/app -p '*.py' --recursive -- 
             python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
EOF
        
        echo -e "${YELLOW}🛑 停止現有容器...${NC}"
        docker compose -f $COMPOSE_FILE -f docker-compose.dev.yml down
        
        echo -e "${YELLOW}🚀 啟動開發容器...${NC}"
        docker compose -f $COMPOSE_FILE -f docker-compose.dev.yml up -d
        
        # 等待容器啟動
        echo -e "${GRAY}等待容器完全啟動...${NC}"
        sleep 5
        
        # 在容器內執行資料庫遷移
        if [ -f "migrations/migration_manager.py" ]; then
            if [ -f "data/gemini.db" ]; then
                echo -e "${BLUE}🔄 檢查資料庫遷移...${NC}"
                # 先檢查遷移腳本是否存在於容器中
                if docker exec $CONTAINER_NAME ls /app/migrations/migration_manager.py >/dev/null 2>&1; then
                    # 使用新的遷移管理器
                    docker exec $CONTAINER_NAME python /app/migrations/migration_manager.py --quiet || {
                        # 如果失敗，顯示詳細信息
                        echo -e "${YELLOW}⚠️  遷移需要執行，顯示詳細信息：${NC}"
                        docker exec $CONTAINER_NAME python /app/migrations/migration_manager.py
                    }
                else
                    echo -e "${RED}❌ 遷移腳本未找到於容器中，請重新構建映像${NC}"
                fi
            else
                echo -e "${YELLOW}📦 新安裝，尚無資料庫${NC}"
            fi
        fi
        
        if health_check; then
            echo ""
            echo -e "${GREEN}✅ 開發模式啟動完成！${NC}"
            echo -e "${YELLOW}📝 特性：${NC}"
            echo -e "  - 本地代碼已掛載"
            echo -e "  - 修改 .py 文件會自動重載"
            echo -e "  - 實時查看日誌: ${YELLOW}$0 -m logs${NC}"
            show_service_info
        fi
        ;;
        
    stop)
        echo -e "${PURPLE}🛑 停止服務${NC}"
        echo ""
        docker compose -f $COMPOSE_FILE down
        echo -e "${GREEN}✅ 服務已停止${NC}"
        ;;
        
    logs)
        echo -e "${PURPLE}📋 查看日誌${NC}"
        echo -e "${YELLOW}提示: 按 Ctrl+C 退出日誌查看${NC}"
        echo ""
        docker compose -f $COMPOSE_FILE logs -f --tail=100
        # 日誌模式不需要等待按鍵
        exit 0
        ;;
        
    status)
        if [ "$INTERACTIVE" = false ]; then
            echo -e "${PURPLE}📊 服務狀態${NC}"
            echo ""
        fi
        
        # 檢查容器狀態
        if docker ps | grep -q $CONTAINER_NAME; then
            echo -e "${GREEN}✅ 容器運行中${NC}"
            echo ""
            docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(NAMES|$CONTAINER_NAME)"
            
            # 顯示資源使用
            echo ""
            echo -e "${BLUE}📈 資源使用：${NC}"
            docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" | grep -E "(CONTAINER|$CONTAINER_NAME)"
            
            # 健康檢查
            echo ""
            if curl -s http://localhost:$DEFAULT_PORT/health > /dev/null; then
                echo -e "${GREEN}✅ 健康檢查: 正常${NC}"
                show_service_info
            else
                echo -e "${RED}❌ 健康檢查: 失敗${NC}"
            fi
        else
            echo -e "${RED}❌ 容器未運行${NC}"
            echo -e "${YELLOW}啟動服務: $0 -m start${NC}"
        fi
        ;;
        
    *)
        echo -e "${RED}❌ 無效的模式: $MODE${NC}"
        usage
        ;;
esac

# 清理臨時文件
if [ -f "docker-compose.dev.yml" ]; then
    rm -f docker-compose.dev.yml
fi

# 結束時間
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - $(date +%s)))

# 根據模式顯示不同的結束信息
if [ "$MODE" = "logs" ]; then
    exit 0
fi

if [ "$INTERACTIVE" = true ]; then
    # 互動模式下等待用戶按鍵返回選單
    if [ "$MODE" != "stop" ]; then
        wait_for_key
    fi
    # 遞歸調用自己以返回選單
    exec "$0"
else
    # 非互動模式正常結束
    if [ "$MODE" = "stop" ] || [ "$MODE" = "status" ]; then
        echo ""
    else
        echo -e "${CYAN}╔════════════════════════════════════════╗${NC}"
        echo -e "${CYAN}║          ✅ 操作完成                  ║${NC}"
        echo -e "${CYAN}╚════════════════════════════════════════╝${NC}"
    fi
fi