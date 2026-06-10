#!/bin/bash
git config --global credential.helper store
cd "/Library/Claude/Projects/HDE重要KPI管理ダッシュボード"
git remote set-url origin https://github.com/vivihub/mimei-kpi-dashboard.git
echo "https://vivihub:YOUR_GITHUB_TOKEN_HERE@github.com" > ~/.git-credentials
chmod 600 ~/.git-credentials
git push origin main && echo "✅ プッシュ完了！"
