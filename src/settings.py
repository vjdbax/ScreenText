import json
import os
from typing import Dict, Any

class Settings:
    """Класс для управления настройками приложения"""
    
    DEFAULT_SETTINGS = {
        "hotkeys": {
            "ocr": "ctrl+home",
            "translate": "ctrl+end"
        },
        "languages": {
            "ocr": "rus+eng",
            "translate_target": "ru",
            "translator_engine": "google",
            "deepl_api_key": ""
        },
        "llm": {
            "use_smart_translate": False,
            "translate_with_standard_engine": False, # Новая галочка гибридного перевода
            "api_key": "",
            "model": "gpt-4o-mini",
            "base_url": "https://api.openai.com/v1",
            "keys_dict": {}, 
            "models_dict": {} 
        },
        "auto_start": False,
        "window_opacity": 0.80,          
        "border_color": "#FFFFFF",       
        "bg_color": "#000000",           
        "font_color": "#FFFFFF",         
        "font_size_p": 10,               
        "font_size_h2": 12,              
        "font_size_h1": 14,              
        "translate_window_duration": 5000  
    }
    
    def __init__(self, config_dir: str = "ScreenTextHelper"):
        appdata_root = os.environ.get("APPDATA", os.path.expanduser("~"))
        self.config_dir = os.path.join(appdata_root, config_dir)
        self.config_file = os.path.join(self.config_dir, "settings.json")
        self.settings = self.load_settings()
        
    def load_settings(self) -> Dict[str, Any]:
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    merged = self.DEFAULT_SETTINGS.copy()
                    merged.update(loaded)
                    for key in ["hotkeys", "languages", "llm"]:
                        if key in loaded and isinstance(loaded[key], dict):
                            merged[key] = {**self.DEFAULT_SETTINGS[key], **loaded[key]}
                    return merged
            else:
                os.makedirs(self.config_dir, exist_ok=True)
                return self.DEFAULT_SETTINGS.copy()
        except (json.JSONDecodeError, IOError):
            return self.DEFAULT_SETTINGS.copy()
    
    def save_settings(self) -> bool:
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
            return True
        except IOError:
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        self.settings = self.load_settings()
        keys = key.split('.')
        value = self.settings
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def set(self, key: str, value: Any) -> None:
        keys = key.split('.')
        current = self.settings
        for k in keys[:-1]:
            if k not in current or not isinstance(current[k], dict):
                current[k] = {}
            current = current[k]
        current[keys[-1]] = value
    
    def get_hotkey(self, action: str) -> str: return self.get(f"hotkeys.{action}", self.DEFAULT_SETTINGS["hotkeys"][action])
    def set_hotkey(self, action: str, hotkey: str) -> None: self.set(f"hotkeys.{action}", hotkey)
    def get_ocr_language(self) -> str: return self.get("languages.ocr", self.DEFAULT_SETTINGS["languages"]["ocr"])
    def set_ocr_language(self, language: str) -> None: self.set("languages.ocr", language)
    def get_translate_target_language(self) -> str: return self.get("languages.translate_target", self.DEFAULT_SETTINGS["languages"]["translate_target"])
    def set_translate_target_language(self, language: str) -> None: self.set("languages.translate_target", language)
    def get_auto_start(self) -> bool: return self.get("auto_start", self.DEFAULT_SETTINGS["auto_start"])
    def set_auto_start(self, auto_start: bool) -> None: self.set("auto_start", auto_start)
    def reset_to_defaults(self) -> None:
        self.settings = self.DEFAULT_SETTINGS.copy()
        self.save_settings()

settings = Settings()