@echo off
title Bot Teste KD - Python 3.11

echo Instalando dependencias...
py -3.11 -m pip install py-cord requests flask --quiet

echo Iniciando bot...
py -3.11 bot.py

echo Bot parou. Pressione qualquer tecla para fechar...
pause