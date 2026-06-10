#!/bin/bash
cd ~/Documents/Claude/Projects/HDE重要KPI管理ダッシュボード
git push origin master > push_log.txt 2>&1
echo "EXIT_CODE:$?" >> push_log.txt
