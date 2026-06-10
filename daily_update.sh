#!/bin/bash
# 未明シアター KPI ダッシュボード 自動更新スクリプト
# 毎日朝9時に fetch_youtube.py を実行し、結果を GitHub へ Push する

PROJECT_DIR="/Library/Claude/Projects/HDE重要KPI管理ダッシュボード"
LOG_FILE="$PROJECT_DIR/daily_update.log"

echo " =====================================" >> "$LOG_FILE"
echo "$(date '+%Y-%m-%d %H:%M:%S') 自動更新開始" >> "$LOG_FILE"

cd "$PROJECT_DIR" || { echo "フォルダが見つかりません" >> "$LOG_FILE"; exit 1; }

# 1. YouTube APIからデータ取得 → index.html 更新
python3 fetch_youtube.py >> "$LOG_FILE" 2>&1
FETCH_STATUS=$?

if [ $FETCH_STATUS -ne 0 ]; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') ⚠️  fetch_youtube.py でエラーが発生しました (exit $FETCH_STATUS)" >> "$LOG_FILE"
  exit 1
fi

# 2. 変更があればコミット & プッシュ
git add index.html >> "$LOG_FILE" 2>&1

if git diff --cached --quiet; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') 変更なし。スクップ。" >> "$LOG_FILE"
else
  git -c user.name='Shu' -c user.email='shu.1sec@gmail.com' commit -m "自動更新: $(date '+%Y-%m-%d')" >> "$LOG_FILE" 2>&1
  git push origin main >> "$LOG_FILE" 2>&1
  PUSH_STATUS=$?
  if [ $PUSH_STATUS -eq 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') ✅ GitHub へのプッシュ完了" >> "$LOG_FILE"
  else
    echo "$(date '+%Y-%m-%d %H:%M:%S') ⚠️  プッシュ失敗 (exit $PUSH_STATUS)" >> "$LOG_FILE"
  fi
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') 更新完了" >> "$LOG_FILE"
