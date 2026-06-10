#!/bin/bash
# launchd ジョブ再インストール: com.mimei.daily-update
PROJECT_DIR="/Library/Claude/Projects/HDE重要KPI管理ダッシュボード"
PLIST_SRC="$PROJECT_DIR/com.mimei.daily-update.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.mimei.daily-update.plist"
LOG="$PROJECT_DIR/setup_launchd_log.txt"

{
  echo "===== $(date) ====="
  mkdir -p "$HOME/Library/LaunchAgents"
  cp "$PLIST_SRC" "$PLIST_DST" && echo "plist copied -> $PLIST_DST"

  # 既存ジョブを停止（存在しなくてもエラー無視）
  launchctl unload "$PLIST_DST" 2>/dev/null
  launchctl bootout "gui/$(id -u)/com.mimei.daily-update" 2>/dev/null

  # 新しいジョブを読み込み
  if launchctl load "$PLIST_DST" 2>>"$LOG"; then
    echo "launchctl load OK"
  else
    launchctl bootstrap "gui/$(id -u)" "$PLIST_DST" 2>>"$LOG" && echo "launchctl bootstrap OK"
  fi

  echo "--- 登録確認 ---"
  launchctl list | grep mimei || echo "(リスト未検出)"
  echo "EXIT_CODE:$?"
} >> "$LOG" 2>&1
