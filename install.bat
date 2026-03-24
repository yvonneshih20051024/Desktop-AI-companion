@echo off
chcp 65001 > nul
:: 将下方的路径替换为你电脑中实际的 activate.bat 路径
call C:\Users\SYN17\anaconda3\Scripts\activate.bat pet_env

echo 正在安装必要的依赖库...
pip install PyQt6 requests
pip install pyautogui Pillow

echo 安装完毕！
pause