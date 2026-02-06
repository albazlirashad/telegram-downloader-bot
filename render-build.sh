#!/usr/bin/env bash
# تثبيت ffmpeg و nodejs
# Render سيقوم بتشغيل هذا كـ root تلقائياً عند استخدامه بشكل صحيح
apt-get update && apt-get install -y ffmpeg nodejs

# تثبيت مكتبات بايثون
pip install -r requirements.txt
