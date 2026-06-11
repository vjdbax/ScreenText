#!/usr/bin/env python3
"""
Запуск ScreenText Helper
"""

import sys
import os

# Добавляем директорию src в sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from main_app import main

if __name__ == "__main__":
    sys.exit(main())