#!/usr/bin/env bash

# تحديث النظام وتثبيت FFmpeg و Node.js
apt-get -y update
apt-get -y install ffmpeg nodejs

# تثبيت مكتبات البايثون الموجودة في الملف السابق
pip install -r requirements.txt