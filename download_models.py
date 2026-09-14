#!/usr/bin/env python3
"""
Pre-download EasyOCR models before PyInstaller build.
Run BEFORE compilation to cache models locally and bundle them.
"""
import os
import sys

# Указываем путь к моделям (локальная папка, чтобы PyInstaller подхватил)
models_dir = os.path.join(os.path.dirname(__file__), "easyocr_models")
os.environ["EASYOCR_MODULE_PATH"] = models_dir
os.makedirs(models_dir, exist_ok=True)

print("=" * 60)
print("Downloading EasyOCR models...")
print(f"Target: {models_dir}")
print("=" * 60)

# Импортируем easyocr — он скачает модели в EASYOCR_MODULE_PATH
import easyocr
reader = easyocr.Reader(["ru", "en"])

print("=" * 60)
print("[SUCCESS] Models downloaded to:", models_dir)
print("Files:")
for f in os.listdir(models_dir):
    fpath = os.path.join(models_dir, f)
    size = os.path.getsize(fpath)
    print(f"  {f}  ({size / 1024 / 1024:.1f} MB)")
print("=" * 60)
print("Ready for PyInstaller compilation.")
