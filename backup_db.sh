#!/bin/bash

# Database Backup Script for Korzinka
# Creates timestamped PostgreSQL database dumps

set -e  # Exit on any error

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Backup configuration
BACKUP_DIR="$SCRIPT_DIR/backups/db"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="korzinka_backup_${TIMESTAMP}.sql"
BACKUP_PATH="$BACKUP_DIR/$BACKUP_FILE"

# Database credentials (hardcoded for stability)
DB_HOST="localhost"
DB_PORT="5432"
DB_NAME="korzinka"
DB_USER="korzinka_user"
DB_PASSWORD="korzinka_pass"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Korzinka Database Backup${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}Database:${NC} $DB_NAME"
echo -e "${YELLOW}Host:${NC} $DB_HOST:$DB_PORT"
echo -e "${YELLOW}Backup file:${NC} $BACKUP_FILE"
echo ""

# Create database dump
echo -e "${GREEN}Creating database backup...${NC}"
PGPASSWORD="$DB_PASSWORD" pg_dump \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --format=plain \
    --file="$BACKUP_PATH" \
    2>&1 > /dev/null

# Check if backup was created successfully
if [ -f "$BACKUP_PATH" ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_PATH" | cut -f1)
    echo ""
    echo -e "${GREEN}✅ Backup created successfully!${NC}"
    echo -e "${YELLOW}File:${NC} $BACKUP_PATH"
    echo -e "${YELLOW}Size:${NC} $BACKUP_SIZE"

    # Compress the backup
    echo ""
    echo -e "${GREEN}Compressing backup...${NC}"
    gzip "$BACKUP_PATH"
    COMPRESSED_PATH="${BACKUP_PATH}.gz"
    COMPRESSED_SIZE=$(du -h "$COMPRESSED_PATH" | cut -f1)

    echo -e "${GREEN}✅ Backup compressed!${NC}"
    echo -e "${YELLOW}Compressed file:${NC} $COMPRESSED_PATH"
    echo -e "${YELLOW}Compressed size:${NC} $COMPRESSED_SIZE"

    # Keep only last 10 backups
    echo ""
    echo -e "${GREEN}Cleaning old backups (keeping last 10)...${NC}"
    cd "$BACKUP_DIR"
    ls -t korzinka_backup_*.sql.gz | tail -n +11 | xargs -r rm
    BACKUP_COUNT=$(ls -1 korzinka_backup_*.sql.gz 2>/dev/null | wc -l)
    echo -e "${GREEN}✅ Total backups: $BACKUP_COUNT${NC}"

    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Backup completed successfully!${NC}"
    echo -e "${GREEN}========================================${NC}"
else
    echo ""
    echo -e "${RED}❌ Backup failed!${NC}"
    exit 1
fi
