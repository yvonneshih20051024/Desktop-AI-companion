@echo off
chcp 65001 > nul
:: 请将下面的路径修改为你电脑上实际的 activate.bat 路径
call C:\Users\SYN17\anaconda3\Scripts\activate.bat pet_env

:: 激活环境后，切换到脚本目录
cd /d C:\Users\SYN17\Desktop\pet\

:: 运行你的程序
python oc.py
pause