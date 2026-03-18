#!/bin/bash
# 备份workspace关键配置文件
# 用法: ./backup_workspace.sh

VERSION="V6.2.1"
DATE=$(date +%Y-%m-%d)
TIME=$(date +%H-%M-%S)
BACKUP_DIR="/Users/roberto/.openclaw/workspace/workspace_backups/${VERSION}_${DATE}_${TIME}"

mkdir -p "$BACKUP_DIR"

# 复制关键文件
cp /Users/roberto/.openclaw/workspace/SOUL.md "$BACKUP_DIR/"
cp /Users/roberto/.openclaw/openclaw.json "$BACKUP_DIR/"
cp /Users/roberto/.openclaw/workspace/USER.md "$BACKUP_DIR/"
cp /Users/roberto/.openclaw/workspace/IDENTITY.md "$BACKUP_DIR/"
cp /Users/roberto/.openclaw/workspace/AGENTS.md "$BACKUP_DIR/"
cp /Users/roberto/.openclaw/workspace/HEARTBEAT.md "$BACKUP_DIR/"

echo "✅ 备份完成: $BACKUP_DIR"
ls -la "$BACKUP_DIR"
