#!/bin/bash
# Скрипт для запуска ВСЕХ или ОДНОГО сервиса Korzinka (совместимый с разными версиями Bash)

set -e  # Выходим при любой ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Конфигурация сервисов (используем простые массивы для совместимости)
SERVICE_NAMES=("telegram-bot" "rpa-service" "user-service" "order-service" "promotion-service")
SERVICE_PATHS=("services/telegram-bot/main.py" "services/rpa-service/main.py" "services/user-service/main.py" "services/order-service/main.py" "services/promotion-service/main.py")
SERVICE_PORTS=(8001 8004 8002 8003 8005)

# Рабочая директория
PROJECT_DIR="/Users/ss/GenAI/korzinka"
LOGS_DIR="$PROJECT_DIR/logs"
PIDS_FILE="$PROJECT_DIR/.service_pids"

# Глобальная переменная для режима работы
SINGLE_SERVICE_MODE=false
TARGET_SERVICE_NAME=""

# Функция для логирования
log() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%H:%M:%S')] ❌ ERROR: $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%H:%M:%S')] ⚠️  WARNING: $1${NC}"
}

info() {
    echo -e "${PURPLE}[$(date +'%H:%M:%S')] ℹ️  INFO: $1${NC}"
}

# Показать справку
show_usage() {
    echo -e "${CYAN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║         KORZINKA SERVICES MANAGER - USAGE             ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════╝${NC}"
    echo
    echo -e "${BLUE}SYNOPSIS:${NC}"
    echo -e "  ./start_services.sh [SERVICE_NAME]"
    echo
    echo -e "${BLUE}DESCRIPTION:${NC}"
    echo -e "  Start all services or restart a specific service"
    echo
    echo -e "${BLUE}OPTIONS:${NC}"
    echo -e "  ${GREEN}No arguments${NC}     - Start all services (full cleanup)"
    echo -e "  ${GREEN}SERVICE_NAME${NC}     - Restart specific service (clean only its logs)"
    echo -e "  ${GREEN}--help, -h${NC}       - Show this help message"
    echo
    echo -e "${BLUE}AVAILABLE SERVICES:${NC}"
    echo -e "  ${YELLOW}Short Name       Full Name           Port${NC}"
    echo -e "  ${GREEN}telegram, bot${NC}    telegram-bot        8001"
    echo -e "  ${GREEN}rpa${NC}              rpa-service         8004"
    echo -e "  ${GREEN}user${NC}             user-service        8002"
    echo -e "  ${GREEN}order${NC}            order-service       8003"
    echo -e "  ${GREEN}promotion${NC}        promotion-service   8005"
    echo
    echo -e "${BLUE}EXAMPLES:${NC}"
    echo -e "  ${CYAN}# Start all services${NC}"
    echo -e "  ./start_services.sh"
    echo
    echo -e "  ${CYAN}# Restart RPA service only${NC}"
    echo -e "  ./start_services.sh rpa"
    echo
    echo -e "  ${CYAN}# Restart Telegram bot${NC}"
    echo -e "  ./start_services.sh telegram"
    echo
}

# Нормализация имени сервиса (короткое -> полное)
normalize_service_name() {
    local input_name="$1"
    
    case "$input_name" in
        telegram|bot)
            echo "telegram-bot"
            ;;
        rpa)
            echo "rpa-service"
            ;;
        user)
            echo "user-service"
            ;;
        order)
            echo "order-service"
            ;;
        promotion)
            echo "promotion-service"
            ;;
        telegram-bot|rpa-service|user-service|order-service|promotion-service)
            echo "$input_name"
            ;;
        *)
            echo ""
            ;;
    esac
}

# Получить индекс сервиса по имени
get_service_index_by_name() {
    local service_name="$1"
    
    for i in $(seq 0 $((${#SERVICE_NAMES[@]} - 1))); do
        if [[ "${SERVICE_NAMES[$i]}" == "$service_name" ]]; then
            echo "$i"
            return 0
        fi
    done
    
    return 1
}

# Парсинг аргументов командной строки
parse_arguments() {
    if [[ "$#" -eq 0 ]]; then
        # Нет аргументов - запуск всех сервисов
        SINGLE_SERVICE_MODE=false
        return 0
    fi
    
    local arg="$1"
    
    # Проверка на справку
    if [[ "$arg" == "--help" || "$arg" == "-h" ]]; then
        show_usage
        exit 0
    fi
    
    # Нормализуем имя сервиса
    local normalized=$(normalize_service_name "$arg")
    
    if [[ -z "$normalized" ]]; then
        error "Unknown service: $arg"
        echo
        show_usage
        exit 1
    fi
    
    # Проверяем что такой сервис существует
    if ! get_service_index_by_name "$normalized" >/dev/null 2>&1; then
        error "Service not found in configuration: $normalized"
        exit 1
    fi
    
    SINGLE_SERVICE_MODE=true
    TARGET_SERVICE_NAME="$normalized"
    
    return 0
}

# Получение порта по индексу сервиса
get_service_port() {
    local index=$1
    echo "${SERVICE_PORTS[$index]}"
}

# Получение пути по индексу сервиса
get_service_path() {
    local index=$1
    echo "${SERVICE_PATHS[$index]}"
}

# Получение имени по индексу сервиса
get_service_name() {
    local index=$1
    echo "${SERVICE_NAMES[$index]}"
}

# Очистка логов одного сервиса
clean_service_logs() {
    local service_name="$1"
    local log_file="$LOGS_DIR/${service_name}.log"
    
    if [[ -f "$log_file" ]]; then
        local filesize=$(ls -lah "$log_file" 2>/dev/null | awk '{print $5}' || echo "unknown")
        info "Cleaning log file: ${service_name}.log ($filesize)"
        rm -f "$log_file"
        log "✅ Log file cleaned"
    else
        info "No existing log file for $service_name"
    fi
}

# Проверка рабочей директории
check_project_dir() {
    if [[ ! -d "$PROJECT_DIR" ]]; then
        error "Project directory not found: $PROJECT_DIR"
        exit 1
    fi
    
    cd "$PROJECT_DIR"
    log "Changed to project directory: $PROJECT_DIR"
    
    if [[ "$SINGLE_SERVICE_MODE" == false ]]; then
        # Полная очистка директории логов при запуске всех сервисов
        clean_logs_directory
    fi
    
    # Создаем директорию для логов если её нет
    mkdir -p "$LOGS_DIR"
    log "Logs directory ready: $LOGS_DIR"
}

# Полная очистка директории логов
clean_logs_directory() {
    if [[ -d "$LOGS_DIR" ]]; then
        log "🧹 Cleaning logs directory: $LOGS_DIR"
        
        # Подсчитываем файлы и статистику для информации
        local file_count=$(find "$LOGS_DIR" -type f 2>/dev/null | wc -l | tr -d ' ')
        local dir_size="N/A"
        
        # Получаем размер директории
        if command -v du >/dev/null 2>&1; then
            dir_size=$(du -sh "$LOGS_DIR" 2>/dev/null | cut -f1 || echo "N/A")
        fi
        
        if [[ "$file_count" -gt 0 ]]; then
            info "Found $file_count log files ($dir_size total) to clean"
            
            # Показываем основные файлы логов (первые 5)
            if [[ "$file_count" -le 10 ]]; then
                info "Files to be removed:"
                find "$LOGS_DIR" -type f -name "*.log" 2>/dev/null | head -5 | while read -r file; do
                    local filename=$(basename "$file")
                    local filesize="unknown"
                    if [[ -f "$file" ]]; then
                        filesize=$(ls -lah "$file" 2>/dev/null | awk '{print $5}' || echo "unknown")
                    fi
                    info "  - $filename ($filesize)"
                done
            fi
            
            # Удаляем все файлы и поддиректории
            rm -rf "${LOGS_DIR}"/* 2>/dev/null || true
            rm -rf "${LOGS_DIR}"/.[^.]* 2>/dev/null || true  # Скрытые файлы
            
            log "✅ Logs directory cleaned successfully ($file_count files removed)"
        else
            log "📁 Logs directory is already empty"
        fi
    else
        log "📁 Logs directory doesn't exist, will create new one"
    fi
}

# Проверка виртуального окружения
check_venv() {
    if [[ ! -f "./venv/bin/python3" ]]; then
        error "Virtual environment not found at ./venv/"
        error "Please create virtual environment first"
        exit 1
    fi
    
    log "Virtual environment found"
}

# Проверка .env файла
check_env() {
    if [[ ! -f ".env" ]]; then
        error ".env file not found"
        error "Please create .env file with required environment variables"
        exit 1
    fi

    log ".env file found"
}

# Очистка зависших транзакций в БД
cleanup_stuck_db_transactions() {
    log "🧹 Cleaning stuck database transactions..."

    ./venv/bin/python3 -c "
import asyncio
import sys
sys.path.insert(0, '$PROJECT_DIR')

from shared.utils.db_cleanup import kill_stuck_transactions

result = asyncio.run(kill_stuck_transactions(idle_threshold_seconds=180))
print(f'Killed {result} stuck transaction(s)' if result > 0 else 'No stuck transactions found')
" 2>&1 | grep -v "sqlalchemy.engine" | grep -v "BEGIN\|ROLLBACK" | while read -r line; do
        if [[ "$line" =~ "Killed" || "$line" =~ "No stuck" ]]; then
            log "$line"
        fi
    done

    log "✅ Database cleanup completed"
}

# Поиск процессов на порту
find_processes_on_port() {
    local port=$1
    lsof -ti :$port 2>/dev/null || true
}

# Мягкое завершение процесса
soft_kill() {
    local pid=$1
    local service_name=$2
    
    if kill -0 "$pid" 2>/dev/null; then
        info "Sending SIGTERM to $service_name (PID: $pid)"
        kill -TERM "$pid" 2>/dev/null || true
        
        # Ждем до 5 секунд
        local count=0
        while kill -0 "$pid" 2>/dev/null && [[ $count -lt 5 ]]; do
            sleep 1
            ((count++))
        done
        
        if kill -0 "$pid" 2>/dev/null; then
            return 1  # Процесс еще жив
        else
            log "$service_name (PID: $pid) terminated gracefully"
            return 0
        fi
    fi
    return 0
}

# Жесткое завершение процесса
hard_kill() {
    local pid=$1
    local service_name=$2
    
    if kill -0 "$pid" 2>/dev/null; then
        warn "Force killing $service_name (PID: $pid)"
        kill -KILL "$pid" 2>/dev/null || true
        sleep 1
        
        if kill -0 "$pid" 2>/dev/null; then
            error "Could not kill $service_name (PID: $pid)"
            return 1
        else
            log "$service_name (PID: $pid) force killed"
            return 0
        fi
    fi
    return 0
}

# Остановка одного сервиса
stop_single_service() {
    local service_name="$1"
    local service_index=$(get_service_index_by_name "$service_name")
    local port=$(get_service_port "$service_index")
    
    log "🛑 Stopping $service_name..."
    
    local pids=$(find_processes_on_port "$port")
    
    if [[ -z "$pids" ]]; then
        info "No running processes found on port $port"
        return 0
    fi
    
    info "Found processes on port $port for $service_name"
    
    # Пробуем мягкое завершение для каждого PID
    for pid in $pids; do
        if ! soft_kill "$pid" "$service_name"; then
            # Если мягкое завершение не сработало, применяем жесткое
            hard_kill "$pid" "$service_name"
        fi
    done
    
    log "Waiting 2 seconds for cleanup..."
    sleep 2
    
    # Проверяем что порт освободился
    local remaining_pids=$(find_processes_on_port "$port")
    if [[ -n "$remaining_pids" ]]; then
        error "Port $port is still occupied after cleanup"
        return 1
    fi
    
    log "✅ $service_name stopped successfully"
    return 0
}

# Остановка всех зависших сессий
stop_hanging_sessions() {
    log "🛑 Stopping hanging sessions..."
    
    local stopped_any=false
    
    # Проходим по всем портам сервисов
    for i in $(seq 0 $((${#SERVICE_NAMES[@]} - 1))); do
        local service_name=$(get_service_name $i)
        local port=$(get_service_port $i)
        
        local pids=$(find_processes_on_port "$port")
        
        if [[ -n "$pids" ]]; then
            stopped_any=true
            info "Found processes on port $port for $service_name"
            
            # Пробуем мягкое завершение для каждого PID
            for pid in $pids; do
                if ! soft_kill "$pid" "$service_name"; then
                    # Если мягкое завершение не сработало, применяем жесткое
                    hard_kill "$pid" "$service_name"
                fi
            done
        fi
    done
    
    # Дополнительная очистка - ищем Python процессы связанные с проектом
    log "🔍 Checking for remaining Korzinka Python processes..."
    
    local korzinka_pids=$(ps aux | grep python | grep korzinka | grep main.py | awk '{print $2}' | grep -E '^[0-9]+$' || true)
    
    if [[ -n "$korzinka_pids" ]]; then
        stopped_any=true
        for pid in $korzinka_pids; do
            info "Found Korzinka Python process (PID: $pid)"
            if ! soft_kill "$pid" "Korzinka-Python"; then
                hard_kill "$pid" "Korzinka-Python"
            fi
        done
    fi
    
    if [[ "$stopped_any" == "true" ]]; then
        log "Waiting 3 seconds for cleanup..."
        sleep 3
    else
        log "No hanging sessions found"
    fi
    
    # Очищаем файл с PID
    rm -f "$PIDS_FILE"
    log "Cleaned up PID file"
}

# Проверка доступности порта
check_port_free() {
    local port=$1
    local pids=$(find_processes_on_port "$port")
    
    if [[ -n "$pids" ]]; then
        return 1  # Порт занят
    else
        return 0  # Порт свободен
    fi
}

# Запуск отдельного сервиса
start_service() {
    local service_index=$1
    local service_name=$(get_service_name $service_index)
    local service_path=$(get_service_path $service_index)
    local port=$(get_service_port $service_index)
    
    info "Starting $service_name..."
    
    # Проверяем что файл сервиса существует
    if [[ ! -f "$service_path" ]]; then
        error "Service file not found: $service_path"
        return 1
    fi
    
    # Проверяем что порт свободен
    if ! check_port_free "$port"; then
        error "Port $port is still occupied for $service_name"
        return 1
    fi
    
    # Создаем лог файл
    local log_file="$LOGS_DIR/${service_name}.log"
    echo "=== $service_name START: $(date) ===" > "$log_file"

    # Запускаем сервис с SERVICE_NAME для идентификации в PostgreSQL
    SERVICE_NAME="$service_name" nohup ./venv/bin/python3 "$service_path" >> "$log_file" 2>&1 &
    local pid=$!
    
    # Сохраняем PID
    echo "${service_name}_PID=$pid" >> "$PIDS_FILE"
    
    # Ждем немного для запуска
    sleep 2
    
    # Проверяем что процесс запустился
    if kill -0 "$pid" 2>/dev/null; then
        log "$service_name started successfully (PID: $pid, Port: $port)"
        info "Logs: tail -f $log_file"
        return 0
    else
        error "$service_name failed to start"
        error "Check logs: cat $log_file"
        return 1
    fi
}

# Проверка здоровья сервиса
check_service_health() {
    local service_index=$1
    local service_name=$(get_service_name $service_index)
    local port=$(get_service_port $service_index)
    
    local pids=$(find_processes_on_port "$port")
    
    if [[ -n "$pids" ]]; then
        log "$service_name is healthy on port $port (PID: $pids)"
        return 0
    else
        error "$service_name is not responding on port $port"
        return 1
    fi
}

# Перезапуск одного сервиса
restart_single_service() {
    local service_name="$1"
    
    echo -e "${CYAN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║      🔄 RESTARTING SINGLE SERVICE MODE               ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════╝${NC}"
    
    local service_index=$(get_service_index_by_name "$service_name")
    local port=$(get_service_port "$service_index")
    local log_file="$LOGS_DIR/${service_name}.log"
    
    echo
    info "Service: ${GREEN}$service_name${NC}"
    info "Port: ${GREEN}$port${NC}"
    info "Log file: ${GREEN}$log_file${NC}"
    echo
    
    # Шаг 1: Очистка логов
    log "📋 Step 1/4: Cleaning service logs..."
    clean_service_logs "$service_name"
    
    # Шаг 2: Остановка сервиса
    log "📋 Step 2/4: Stopping service..."
    if ! stop_single_service "$service_name"; then
        error "Failed to stop $service_name"
        exit 1
    fi
    
    # Шаг 3: Запуск сервиса
    log "📋 Step 3/4: Starting service..."
    if ! start_service "$service_index"; then
        error "Failed to start $service_name"
        exit 1
    fi
    
    # Шаг 4: Проверка здоровья
    log "📋 Step 4/4: Checking service health..."
    sleep 1
    
    if check_service_health "$service_index"; then
        echo
        log "╔════════════════════════════════════════════════════════╗"
        log "║  🎉 SERVICE RESTARTED SUCCESSFULLY!                   ║"
        log "╚════════════════════════════════════════════════════════╝"
        echo
        log "✅ Service: $service_name"
        log "✅ Port: http://localhost:$port"
        log "✅ Fresh logs: $log_file"
        echo
        log "📋 MONITORING COMMANDS:"
        log "   tail -f $log_file"
        log "   grep -i error $log_file"
        echo
    else
        error "Service health check failed"
        error "Check logs: cat $log_file"
        exit 1
    fi
}

# Запуск всех сервисов
start_all_services() {
    echo -e "${BLUE}🚀 KORZINKA SERVICES MANAGER${NC}"
    echo -e "${BLUE}=============================${NC}"
    echo -e "${YELLOW}⚠️  LOGS WILL BE COMPLETELY CLEARED${NC}"
    echo -e "${PURPLE}Services to start:${NC}"
    echo -e "${PURPLE}- telegram-bot    (8001) - Telegram bot interface${NC}"
    echo -e "${PURPLE}- user-service    (8002) - User management${NC}" 
    echo -e "${PURPLE}- order-service   (8003) - Order processing${NC}"
    echo -e "${PURPLE}- rpa-service     (8004) - RPA automation${NC}"
    echo -e "${PURPLE}- promotion-service (8005) - Promotions & coupons${NC}"
    echo
    
    log "🚀 Starting all services..."
    
    local failed_services=()
    local started_services=()
    
    # Запускаем каждый сервис
    for i in $(seq 0 $((${#SERVICE_NAMES[@]} - 1))); do
        local service_name=$(get_service_name $i)
        
        if start_service $i; then
            started_services+=($i)
        else
            failed_services+=("$service_name")
        fi
        
        # Небольшая пауза между запусками
        sleep 1
    done
    
    # Проверяем здоровье всех сервисов
    log "🔍 Checking service health..."
    
    local unhealthy_services=()
    
    for i in "${started_services[@]}"; do
        if ! check_service_health $i; then
            local service_name=$(get_service_name $i)
            unhealthy_services+=("$service_name")
        fi
    done
    
    # Итоговый отчет
    echo
    log "📊 STARTUP SUMMARY"
    log "=================="
    
    if [[ ${#failed_services[@]} -eq 0 && ${#unhealthy_services[@]} -eq 0 ]]; then
        log "🎉 ALL SERVICES STARTED SUCCESSFULLY!"
        echo
        log "✅ Running Services:"
        for i in $(seq 0 $((${#SERVICE_NAMES[@]} - 1))); do
            local service_name=$(get_service_name $i)
            local port=$(get_service_port $i)
            log "   - $service_name: http://localhost:$port"
        done
        
        echo
        log "📁 Fresh logs available at: $LOGS_DIR"
        log "🧹 All previous logs were cleared at startup"
        
        echo
        log "🧪 READY FOR TESTING"
        log "===================="
        log "1. 📱 Telegram Bot: Send /start to your bot"
        log "2. 🔑 RPA Authorization: Try Yandex QR flow"
        log "3. 👀 Monitor RPA logs: tail -f logs/rpa-service.log"
        log "4. 🎯 Look for in RPA logs:"
        log "   - ✅ Executing step verify_success"
        log "   - ✅ SUCCESS step verify_success completed!"
        log "   - ✅ Force-executing critical step after success"
        log "   - ✅ Browser FORCE-CLOSED"
        
        echo
        log "📋 MONITORING COMMANDS:"
        log "   # RPA Service (main focus)"
        log "   tail -f logs/rpa-service.log"
        log "   # All services"
        log "   tail -f logs/*.log"
        log "   # Search for verify_success"
        log "   grep -i verify_success logs/rpa-service.log"
        
    else
        error "🚨 SOME SERVICES FAILED!"
        
        if [[ ${#failed_services[@]} -gt 0 ]]; then
            error "Failed to start: ${failed_services[*]}"
        fi
        
        if [[ ${#unhealthy_services[@]} -gt 0 ]]; then
            error "Unhealthy services: ${unhealthy_services[*]}"
        fi
        
        log "Check individual logs in logs/ directory"
    fi
    
    echo
    log "🛑 To stop all services: ./stop_services.sh"
    log "🔄 To restart a service: ./start_services.sh <service_name>"
    log "📊 Service PIDs saved in: $PIDS_FILE"
}

# Главная функция
main() {
    # Парсим аргументы
    parse_arguments "$@"
    
    log "Starting Korzinka Services Manager..."
    
    # Предварительные проверки
    check_project_dir
    check_venv
    check_env
    
    if [[ "$SINGLE_SERVICE_MODE" == true ]]; then
        # Режим перезапуска одного сервиса
        restart_single_service "$TARGET_SERVICE_NAME"
    else
        # Режим запуска всех сервисов
        # Останавливаем зависшие сессии
        stop_hanging_sessions

        # Очищаем зависшие транзакции в БД
        cleanup_stuck_db_transactions

        # Запускаем все сервисы
        start_all_services
    fi
    
    log "🎉 Service startup process completed!"
}

# Запуск
main "$@"
