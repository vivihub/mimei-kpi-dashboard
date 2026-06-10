#!/bin/bash
cd ~/Documents/Claude/Projects/HDE重要KPI管理ダッシュボード
python3 fetch_youtube.py > fetch_log.txt 2>&1
echo "EXIT_CODE:$?" >> fetch_log.txt
