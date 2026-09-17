#!/usr/bin/env python3
"""
Constants for ScreenText Helper
"""

# Application info
APP_NAME = "ScreenText Helper"
APP_VERSION = "5.5.0"
APP_AUTHOR = "ScreenText Helper Team"
APP_DESCRIPTION = "Приложение для захвата области экрана, распознавания текста (OCR) и перевода"

# API endpoints
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
OLLAMA_MODELS_URL = "http://localhost:11434/v1/models"
OLLAMA_PULL_URL = "http://localhost:11434/api/pull"
OLLAMA_DELETE_URL = "http://localhost:11434/api/delete"

# Default settings
DEFAULT_WINDOW_OPACITY = 0.80
DEFAULT_BORDER_COLOR = "#FFFFFF"
DEFAULT_BG_COLOR = "#000000"
DEFAULT_FONT_COLOR = "#FFFFFF"
DEFAULT_FONT_SIZE_P = 10
DEFAULT_FONT_SIZE_H2 = 12
DEFAULT_FONT_SIZE_H1 = 14
DEFAULT_TRANSLATE_WINDOW_DURATION = 5000

# OCR settings
OCR_CONFIDENCE_THRESHOLD = 0.4
OCR_INITIALIZATION_DELAY_SEC = 3.0
OCR_POLL_INTERVAL_MS = 250
OCR_MAX_POLL_COUNTER = 80

# Hotkeys
DEFAULT_OCR_HOTKEY = "ctrl+home"
DEFAULT_TRANSLATE_HOTKEY = "ctrl+end"

# Languages
DEFAULT_OCR_LANGUAGE = "rus+eng"
DEFAULT_TRANSLATE_TARGET = "ru"
DEFAULT_TRANSLATOR_ENGINE = "google"

# LLM settings
DEFAULT_LLM_MODEL = "gpt-4o-mini"
DEFAULT_LLM_BASE_URL = "https://api.openai.com/v1"
DEFAULT_LLM_USE_SMART_TRANSLATE = False
DEFAULT_LLM_TRANSLATE_WITH_STANDARD_ENGINE = False

# UI settings
MIN_OVERLAY_WIDTH = 450
MIN_OVERLAY_HEIGHT = 160
INITIAL_OVERLAY_WIDTH = 450
OVERLAY_BUTTON_HEIGHT = 28

# Error messages
ERROR_OCR_UNAVAILABLE = "OCR недоступен ❌ (EasyOCR не загружен)"
ERROR_API_KEY_MISSING = "Ключ API не найден"
ERROR_MODEL_NO_IMAGE_SUPPORT = "Модель не поддерживает изображения"
ERROR_TRANSLATION_FAILED = "Ошибка перевода ❌"
ERROR_TEXT_NOT_SELECTED = "Ошибка: текст не выделен ❌"
ERROR_NETWORK = "Ошибка связи"
ERROR_API = "Ошибка запроса"

# Success messages
SUCCESS_TRANSLATION_RECEIVED = "Перевод получен! 🎉"
SUCCESS_AI_READY = "ИИ готов!"
SUCCESS_OCR_READY = "OCR готов!"

# Status messages
STATUS_INITIALIZING = "Подготовка..."
STATUS_AI_PROCESSING = "ИИ обрабатывает область..."
STATUS_STANDARD_TRANSLATION = "Стандартный перевод..."
STATUS_GOOGLE_UNAVAILABLE = "Google недоступен, перевод через ИИ..."
STATUS_COPYING_TEXT = "Копирование текста..."
STATUS_TRANSLATING_TEXT = "Перевод текста..."
STATUS_READY = "Готов к работе! 👍"
