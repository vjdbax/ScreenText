#!/usr/bin/env python3
"""
Translation management for ScreenText Helper
"""

import logging
import re
import time
from typing import Optional, Dict, Any
from deep_translator import GoogleTranslator
from settings import settings


def cyrillic_to_lacinka(text: str) -> str:
    """
    Высокоточный локальный конвертер белорусской кириллицы в классическую белорусскую латиницу (Biełaruskaja łacinka)
    """
    # 1. Замены для буквосочетаний с мягким знаком (сь, зь, ць, нь, дзь, ль)
    replacements = {
        "дзь": "dź", "Дзь": "Dź", "ДЗЬ": "DŹ",
        "зь": "ź", "Зь": "Ź", "ЗЬ": "Ź",
        "сь": "ś", "Сь": "Ś", "СЬ": "Ś",
        "ць": "ć", "Ць": "Ć", "ЦЬ": "Ć",
        "нь": "ń", "Нь": "Ń", "НЬ": "Ń",
        "ль": "l", "Ль": "L", "ЛЬ": "L"
    }
    for cyr, lat in replacements.items():
        text = text.replace(cyr, lat)

    # 2. Буква "Л" перед е, ё, і, ю, я становится l, в остальных случаях ł
    text = re.sub(r'([лЛ])([еёіюяеёіюя])', lambda m: ("L" if m.group(1).isupper() else "l") + m.group(2), text)
    text = text.replace("л", "ł").replace("Л", "Ł")

    # 3. Обработка е, ё, ю, я после согласных бвгджзкймнпрстфхцчш (я -> ia, ю -> iu, е -> ie, ё -> io)
    consonants = "бвгджзкймнпрстфхцчшśźćń"
    def replace_soft_vowels(match):
        prev = match.group(1)
        vowel = match.group(2)
        is_upper = vowel.isupper()
        mapping = {"е": "ie", "ё": "io", "ю": "iu", "я": "ia"}
        val = mapping.get(vowel.lower(), vowel)
        if is_upper:
            val = val.capitalize()
        return prev + val

    text = re.sub(r'([' + consonants + r'])([еёюя])', replace_soft_vowels, text)
    text = re.sub(r'([' + consonants.upper() + r'])([ЕЁЮЯ])', replace_soft_vowels, text)

    # 4. Обработка е, ё, ю, я после l/L (я -> a, ю -> u, е -> e, ё -> o)
    def replace_l_vowels(match):
        prev = match.group(1)
        vowel = match.group(2)
        is_upper = vowel.isupper()
        mapping = {"е": "e", "ё": "o", "ю": "u", "я": "a"}
        val = mapping.get(vowel.lower(), vowel)
        if is_upper:
            val = val.upper()
        return prev + val

    text = re.sub(r'([lL])([еёюяЕЁЮЯ])', replace_l_vowels, text)

    # 5. Обработка е, ё, ю, я в начале слова и после гласных -> je, jo, ju, ja
    def replace_initial_vowels(match):
        vowel = match.group(1)
        is_upper = vowel.isupper()
        mapping = {"е": "je", "ё": "jo", "ю": "ju", "я": "ja"}
        val = mapping.get(vowel.lower(), vowel)
        if is_upper:
            val = val.capitalize()
        return val

    text = re.sub(r'\b([еёюяЕЁЮЯ])', replace_initial_vowels, text)
    text = re.sub(r'([аеёіоуэюяыАЕЁІОУЭЮЯЫ\s\.,!?\'"’\-])([еёюяЕЁЮЯ])', lambda m: m.group(1) + replace_initial_vowels(m), text)

    # 6. Посимвольная транслитерация оставшихся букв
    single_replacements = {
        "а": "a", "А": "A",
        "б": "b", "Б": "B",
        "в": "v", "В": "V",
        "г": "h", "Г": "H",
        "д": "d", "Д": "D",
        "ж": "ž", "Ж": "Ž",
        "з": "z", "З": "Z",
        "і": "i", "І": "I",
        "й": "j", "Й": "J",
        "к": "k", "К": "K",
        "м": "m", "М": "M",
        "н": "n", "Н": "N",
        "о": "o", "О": "O",
        "п": "p", "П": "P",
        "р": "r", "Р": "R",
        "с": "s", "С": "S",
        "т": "t", "Т": "T",
        "у": "u", "У": "U",
        "ў": "ŭ", "Ў": "Ŭ",
        "ф": "f", "Ф": "F",
        "х": "ch", "Х": "Ch",
        "ц": "c", "Ц": "C",
        "ч": "č", "Ч": "Č",
        "ш": "š", "Ш": "Š",
        "ы": "y", "Ы": "Y",
        "э": "e", "Э": "E",
        "ь": "", "Ь": ""
    }
    for cyr, lat in single_replacements.items():
        text = text.replace(cyr, lat)

    return text


class TranslatorManager:
    """Класс для управления переводом текста"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.is_ready = True

    def _translate_mymemory(self, text: str, target: str) -> Optional[str]:
        """Резервный переводчик: MyMemory (бесплатно, без ключа)"""
        try:
            from deep_translator import MyMemoryTranslator
            mymemory_langs = {
                'ru': 'russian', 'en': 'english', 'zh': 'chinese',
                'es': 'spanish', 'fr': 'french', 'de': 'german',
                'it': 'italian', 'pt': 'portuguese', 'ar': 'arabic',
                'ja': 'japanese', 'ko': 'korean', 'hi': 'hindi',
                'be': 'belarusian', 'be-latn': 'belarusian'
            }
            ocr_lang = settings.get_ocr_language()
            src_lang = mymemory_langs.get('ru' if ocr_lang == 'rus' else 'en', 'english')
            tgt_lang = mymemory_langs.get(target, 'english')

            if len(text) > 450:
                paragraphs = text.split('\n')
                translated_parts = []
                current_chunk = ""

                for p in paragraphs:
                    if len(current_chunk) + len(p) + 1 < 450:
                        current_chunk += (p + "\n")
                    else:
                        if current_chunk.strip():
                            res = MyMemoryTranslator(source=src_lang, target=tgt_lang).translate(current_chunk.strip())
                            if res and "INVALID SOURCE LANGUAGE" not in res and "MYMEMORY WARNING" not in res:
                                translated_parts.append(res)
                            else:
                                self.logger.error(f"MyMemory chunk error: {res}")
                        current_chunk = p + "\n"
                if current_chunk.strip():
                    res = MyMemoryTranslator(source=src_lang, target=tgt_lang).translate(current_chunk.strip())
                    if res and "INVALID SOURCE LANGUAGE" not in res and "MYMEMORY WARNING" not in res:
                        translated_parts.append(res)
                    else:
                        self.logger.error(f"MyMemory chunk error: {res}")
                return "\n".join(translated_parts) if translated_parts else None
            else:
                result = MyMemoryTranslator(source=src_lang, target=tgt_lang).translate(text)
                if result and "INVALID SOURCE LANGUAGE" not in result and "MYMEMORY WARNING" not in result:
                    return result
                self.logger.error(f"MyMemory вернул ошибку: {result}")
        except Exception as e:
            self.logger.error(f"MyMemory ошибка: {e}")
        return None
        
    def translate_text(self, text: str, target_lang: str = None) -> Optional[str]:
        """Перевод текста (Google → DeepL → MyMemory fallback)"""
        try:
            if not text.strip():
                return None

            print("\n" + "="*50)
            print("[DEBUG] Текст, который отправляется в Google Translate:")
            print(repr(text))
            print("="*50 + "\n")
            
            if target_lang is None:
                target_lang = settings.get("languages.translate_target")
            
            is_lacinka = False
            actual_target = target_lang
            if target_lang == 'be-latn':
                is_lacinka = True
                actual_target = 'be'

            engine = settings.get("languages.translator_engine", "google")

            # 1. Google
            translated = None
            if engine == "google":
                translated = self._try_google(text, actual_target)

            # 2. DeepL
            if not translated and engine == "deepl":
                translated = self._try_deepl(text, actual_target)

            # 3. Fallback: Google → DeepL → MyMemory (если основной движок не сработал)
            if not translated and engine != "google":
                translated = self._try_google(text, actual_target)
            if not translated and engine != "deepl":
                translated = self._try_deepl(text, actual_target)
            if not translated:
                self.logger.info("Переключение на MyMemory API...")
                translated = self._translate_mymemory(text, actual_target)
            
            if translated:
                if is_lacinka:
                    translated = cyrillic_to_lacinka(translated)
                self.logger.info(f"Перевод выполнен: '{text[:50]}...' -> '{translated[:50]}...'")
                return translated
            else:
                self.logger.error("Все переводчики вернули ошибку")
                return None
                
        except Exception as e:
            self.logger.error(f"Ошибка перевода текста: {e}")
            return None

    def _try_google(self, text: str, target: str) -> Optional[str]:
        for attempt in range(2):
            try:
                translated = GoogleTranslator(source='auto', target=target).translate(text)
                if translated:
                    error_markers = ["error 500", "error 429", "server error", "that's an error", "please try again later"]
                    if any(marker in translated.lower() for marker in error_markers):
                        self.logger.error(f"Google вернул ошибку")
                        if attempt == 0:
                            time.sleep(0.5)
                            continue
                        return None
                    return translated
            except Exception as e:
                self.logger.error(f"Google ошибка: {e}")
                if attempt == 0:
                    time.sleep(0.5)
                    continue
                return None
        return None

    def _try_deepl(self, text: str, target: str) -> Optional[str]:
        api_key = settings.get("languages.deepl_api_key", "")
        if not api_key:
            return None
        try:
            from deep_translator import DeeplTranslator
            use_free = api_key.endswith(":fx")
            return DeeplTranslator(api_key=api_key, source='auto', target=target, use_free_api=use_free).translate(text)
        except Exception as e:
            self.logger.error(f"DeepL ошибка: {e}")
        return None
    
    def get_supported_languages(self) -> Dict[str, str]:
        """Получение списка поддерживаемых языков"""
        return {
            'en': 'English',
            'ru': 'Русский',
            'be-latn': 'Biełaruskaja łacinka',
            'zh': 'Chinese',
            'es': 'Spanish',
            'fr': 'French',
            'de': 'German',
            'it': 'Italian',
            'pt': 'Portuguese',
            'ar': 'Arabic',
            'ja': 'Japanese',
            'ko': 'Korean',
            'hi': 'Hindi'
        }
    
    def get_available_language_codes(self) -> list:
        """Получение кодов доступных языков"""
        return list(self.get_supported_languages().keys())
    
    def is_available(self) -> bool:
        """Проверка доступности переводчика"""
        return self.is_ready