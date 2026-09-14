import base64
import requests
import logging
import re
import json
from settings import settings

class SmartTranslator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def encode_image(self, image_path):
        """Кодирование изображения в Base64"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def format_text_to_html(self, text):
        """Автоматическое форматирование сырого текста от ИИ в красивую книжную верстку"""
        if not text.strip():
            return ""
            
        font_color = settings.get("font_color", "#000000")
        p_size = settings.get("font_size_p", 10)
        h1_size = settings.get("font_size_h1", 14)
        
        paragraphs = text.split("\n")
        html_lines = []
        for p in paragraphs:
            p_clean = p.strip()
            if not p_clean:
                continue
            # Если строка выглядит как заголовок (короткая, без знаков препинания или начинается с #)
            if p_clean.startswith("#") or (len(p_clean) < 40 and not p_clean.endswith(('.', '!', '?', '"', '»', ')', ']'))):
                p_title = p_clean.lstrip('#').strip()
                html_lines.append(f'<h1 style="text-align:center; font-family:\'Arial\'; font-size:{h1_size}pt; color:{font_color}; font-weight:bold; margin:10px 0;">{p_title}</h1>')
            else:
                html_lines.append(f'<p style="text-align:justify; text-indent:25px; font-family:\'Georgia\', serif; font-size:{p_size}pt; color:{font_color}; line-height:140%; margin-bottom:8px;">{p_clean}</p>')
        return "".join(html_lines)

    def get_prompt_for_model(self, model_name, target_lang, use_hybrid):
        """База данных промптов с динамической адаптацией под гибридный перевод"""
        model_lower = model_name.lower()
        
        # ЕСЛИ ВКЛЮЧЕН ГИБРИДНЫЙ ПЕРЕВОД: просим ИИ сделать ТОЛЬКО OCR
        if use_hybrid:
            return """
            Perform high-precision OCR on this image. 
            Extract all English text exactly as it appears, preserving the exact paragraphs, structure, and spacing.
            Return ONLY the extracted text. Do not output any markdown blocks (no ```), translation, or explanations.
            """
        
        # 1. Промпт для моделей Qwen
        if "qwen" in model_lower:
            return f"""
            You are a precise OCR and translator. Read the image and translate the text into {target_lang}.
            
            CRITICAL INSTRUCTIONS:
            - Do NOT write any Chinese characters (No hanzi, no 中文 like 身体, 很大, 极小, 眼睛, converted).
            - Use ONLY English (for the Original) and {target_lang} (for the Translation).
            - Keep the layout, lines, and paragraphs exactly as on the image.
            
            Format your response EXACTLY as follows:
            ===ORIGINAL===
            [Put the exact original text extracted from the image here]
            ===TRANSLATION===
            [Put the translated text into {target_lang} here]
            """
            
        # 2. Промпт для моделей MiniCPM
        elif "minicpm" in model_lower:
            return f"""
            Read the text on the image and translate it to {target_lang}.
            
            Format your response EXACTLY as follows:
            ===ORIGINAL===
            [Put the exact original text extracted from the image here]
            ===TRANSLATION===
            [Put the translated text into {target_lang} here]
            """
            
        # 3. Промпт для флагманских моделей (GPT-4o, Gemini)
        elif "gpt" in model_lower or "gemini" in model_lower or "claude" in model_lower:
            return f"""
            You are a professional book translator and advanced OCR engine. 
            Perform high-fidelity OCR on the image and translate the text into {target_lang}.
            Ensure the translation is natural, matches the style of the text, and preserves formatting.
            
            Format your response EXACTLY as follows:
            ===ORIGINAL===
            [Put the exact original text extracted from the image here]
            ===TRANSLATION===
            [Put the translated text into {target_lang} here]
            """
            
        # 4. Базовый надежный промпт-заглушка
        else:
            return f"""
            Extract all text from this image and translate it into {target_lang}.
            
            Format your response EXACTLY as follows:
            ===ORIGINAL===
            [Put the exact original text extracted from the image here]
            ===TRANSLATION===
            [Put the translated text into {target_lang} here]
            """

    def translate_vision(self, image_path, force_direct_translation=False):
        api_key = settings.get("llm.api_key")
        base_url = settings.get("llm.base_url").rstrip('/')
        model = settings.get("llm.model")
        
        lang_code = settings.get("languages.translate_target", "ru")
        lang_mapping = {
            "ru": "Russian", "en": "English", "zh": "Chinese",
            "es": "Spanish", "fr": "French", "de": "German",
            "it": "Italian", "pt": "Portuguese", "ar": "Arabic",
            "ja": "Japanese", "ko": "Korean", "hi": "Hindi",
            "be-latn": "Belarusian language written in traditional Latin script (Biełaruskaja łacinka)"
        }
        target_lang = lang_mapping.get(lang_code, "Russian")

        is_local_ollama = "localhost" in base_url or "127.0.0.1" in base_url
        if not api_key and not is_local_ollama:
            return "<b>Ключ API не найден</b>", "<b>Ошибка:</b> укажите API-ключ в настройках."

        try:
            base64_image = self.encode_image(image_path)
            
            use_hybrid = False if force_direct_translation else settings.get("llm.translate_with_standard_engine", False)
            prompt = self.get_prompt_for_model(model, target_lang, use_hybrid)

            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            
            if is_local_ollama:
                image_payload = f"data:image/jpeg;base64,{base64_image}"
            else:
                image_payload = {"url": f"data:image/jpeg;base64,{base64_image}"}

            payload = {
                "model": model, 
                "messages": [
                    {
                        "role": "user", 
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": image_payload}
                        ]
                    }
                ], 
                "max_tokens": 2000
            }

            response = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=40)

            if response.status_code != 200:
                try:
                    err_data = response.json()
                    err_msg = err_data.get('error', {}).get('message', '') or str(response.status_code)
                except:
                    err_msg = f"HTTP {response.status_code}"
                if any(x in err_msg.lower() for x in ['does not support image', 'not support image', 'cannot read', 'image input', 'image_url']):
                    return (
                        "Модель не поддерживает изображения",
                        f"<b style='color:orange;'>Модель «{model}» не поддерживает изображения.</b><br>"
                        f"Выберите Vision-модель в настройках (например, gpt-4o-mini, qwen2.5vl, gemini-1.5-flash)."
                    )
                return "Ошибка запроса", f"<b style='color:red;'>Ошибка API ({err_msg})</b>"

            res_json = response.json()

            # Проверка на ошибку "модель не поддерживает изображения" в теле ответа
            error_msg = res_json.get('error', {}).get('message', '')
            if any(x in error_msg.lower() for x in ['does not support image', 'not support image', 'cannot read', 'image input', 'image_url']):
                return (
                    "Модель не поддерживает изображения",
                    f"<b style='color:orange;'>Модель «{model}» не поддерживает изображения.</b><br>"
                    f"Выберите Vision-модель в настройках (например, gpt-4o-mini, qwen2.5vl, gemini-1.5-flash)."
                )

            if 'choices' in res_json:
                content = res_json['choices'][0]['message']['content'].strip()
                
                clean_content = content
                if clean_content.startswith("```"):
                    clean_content = re.sub(r'^```[a-zA-Z]*\n', '', clean_content)
                    clean_content = re.sub(r'\n```$', '', clean_content)
                clean_content = clean_content.strip()

                if use_hybrid:
                    orig_html = self.format_text_to_html(clean_content)
                    # ВОЗВРАЩАЕМ СЫРОЙ ТЕКСТ С СОХРАНЕНИЕМ \n ДЛЯ ПРАВИЛЬНОГО ПЕРЕВОДА!
                    return orig_html, clean_content 
                
                orig_txt = ""
                trans_txt = ""
                
                parts = re.split(r'(?i)(?:\*+|_+|#|=|\s)*translation(?:\*+|_+|#|=|\s)*', content)
                
                if len(parts) > 1:
                    orig_part = parts[0]
                    orig_txt = re.sub(r'(?i)(?:\*+|_+|#|=|\s)*original(?:\*+|_+|#|=|\s)*', '', orig_part).strip()
                    trans_txt = parts[1].strip()
                else:
                    trans_txt = content
                    orig_txt = "Не удалось извлечь оригинал отдельно."
                
                orig_html = self.format_text_to_html(orig_txt)
                trans_html = self.format_text_to_html(trans_txt)
                
                return orig_html, trans_html
            else:
                err_msg = res_json.get('error', {}).get('message', 'Неизвестная ошибка API')
                return "Ошибка запроса", f"<b style='color:red;'>Ошибка API:</b> {err_msg}"

        except Exception as e:
            self.logger.error(f"Error: {e}")
            return "Ошибка связи", f"<b style='color:red;'>Ошибка соединения:</b> {str(e)}"