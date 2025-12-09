#!/bin/bash
# Скрипт для остановки всех сервисов Korzinka (совместимый с разными версиями Bash)

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Конфигурация
PROJECT_DIR="/Users/ss/GenAI/korzinka"
PIDS_FILE="$PROJECT_DIR/.service_pids"

# Порты сервисов (только реально существующие)
PORTS=(8001 8002 8003 8004 8005)

echo -e "${BLUE}🛑 KORZINKA SERVICES STOPPER${NC}"
echo -e "${BLUE}=============================${NC}"

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

# Переходим в директорию проекта
cd "$PROJECT_DIR" || { error "Cannot change to project directory"; exit 1; }

# Поиск процессов на порту
find_processes_on_port() {
    local port=$1
    lsof -ti :$port 2>/dev/null || true
}

# Мягкое завершение процесса
soft_kill() {
    local pid=$1
    local name=$2
    
    if kill -0 "$pid" 2>/dev/null; then
        log "Sending SIGTERM to $name (PID: $pid)"
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
            log "$name (PID: $pid) terminated gracefully"
            return 0
        fi
    fi
    return 0
}

# Жесткое завершение процесса
hard_kill() {
    local pid=$1
    local name=$2
    
    if kill -0 "$pid" 2>/dev/null; then
        warn "Force killing $name (PID: $pid)"
        kill -KILL "$pid" 2>/dev/null || true
        sleep 1
        
        if kill -0 "$pid" 2>/dev/null; then
            error "Could not kill $name (PID: $pid)"
            return 1
        else
            log "$name (PID: $pid) force killed"
            return 0
        fi
    fi
    return 0
}

# Остановка сервисов по PID файлу
stop_services_by_pids() {
    if [[ -f "$PIDS_FILE" ]]; then
        log "🔍 Found PID file, stopping services by PID..."
        
        # Читаем PID файл
        while IFS= read -r line; do
            if [[ "$line" =~ ^([^=]+)_PID=([0-9]+)$ ]]; then
                local service_name="${BASH_REMATCH[1]}"
                local pid="${BASH_REMATCH[2]}"
                
                log "Stopping $service_name (PID: $pid)"
                
                if ! soft_kill "$pid" "$service_name"; then
                    hard_kill "$pid" "$service_name"
                fi
            fi
        done < "$PIDS_FILE"
        
        # Удаляем PID файл
        rm -f "$PIDS_FILE"
        log "Removed PID file"
    else
        log "No PID file found, will search by ports"
    fi
}

# Остановка сервисов по портам
stop_services_by_ports() {
    log "🔍 Checking all service ports..."
    
    local found_any=false
    
    for port in "${PORTS[@]}"; do
        local pids=$(find_processes_on_port "$port")
        
        if [[ -n "$pids" ]]; then
            found_any=true
            log "Found processes on port $port"
            
            for pid in $pids; do
                if ! soft_kill "$pid" "Port-$port"; then
                    hard_kill "$pid" "Port-$port"
                fi
            done
        fi
    done
    
    if [[ "$found_any" == "false" ]]; then
        log "No processes found on service ports"
    fi
}

# Дополнительная очистка Python процессов
cleanup_python_processes() {
    log "🔍 Checking for remaining Korzinka Python processes..."
    
    local korzinka_pids=$(ps aux | grep python | grep korzinka | grep main.py | awk '{print $2}' | grep -E '^[0-9]+$' || true)
    
    if [[ -n "$korzinka_pids" ]]; then
        log "Found Korzinka Python processes"
        for pid in $korzinka_pids; do
            if ! soft_kill "$pid" "Korzinka-Python"; then
                hard_kill "$pid" "Korzinka-Python"
            fi
        done
    else
        log "No remaining Korzinka Python processes found"
    fi
}

# Финальная проверка
final_check() {
    log "🔍 Final check..."
    
    local remaining=false
    
    for port in "${PORTS[@]}"; do
        local pids=$(find_processes_on_port "$port")
        if [[ -n "$pids" ]]; then
            error "Port $port still has processes: $pids"
            remaining=true
        fi
    done
    
    if [[ "$remaining" == "false" ]]; then
        log "✅ All service ports are free"
    else
        error "Some processes may still be running"
    fi
}

# Главная функция
main() {
    log "Starting service shutdown process..."
    
    # 1. Останавливаем по PID файлу
    stop_services_by_pids
    
    # 2. Проверяем порты и останавливаем оставшиеся процессы
    stop_services_by_ports
    
    # 3. Дополнительная очистка
    cleanup_python_processes
    
    # 4. Ждем завершения
    log "⏰ Waiting 3 seconds for final cleanup..."
    sleep 3
    
    # 5. Финальная проверка
    final_check
    
    log "🎉 Service shutdown completed!"
    log "All Korzinka services should be stopped"
}

# Запуск
main "$@"
