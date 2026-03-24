@echo off
chcp 65001 > nul
echo 正在打包...
:: --add-data 后面跟着的是 "源文件路径;目标位置"
pyinstaller --noconsole --onefile ^
 --add-data "normal1.png;." ^
 --add-data "normal2.png;." ^
 --add-data "oc.json;." ^
 oc.py
echo 打包完成！请到 dist 文件夹中查看。
pause