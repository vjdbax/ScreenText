import base64
import requests
import logging
import re
import json
from typing import Optional, Callable
from settings import settings
from text_formatter import create_formatter_from_settings

class SmartTranslator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.text_formatter = create_formatter_from_settings()
        self._current_response = None
        self._is_cancelled = False
    
    def cancel(self):
        """Мгновенный разрыв текущего HTTP-запроса"""
        self._is_cancelled = True
        resp = self._current_response
        if resp is not None:
            self._current_response = None
            try:
                resp.close()
            except Exception:
                pass
    
    def reset_cancel(self):
        """Сброс флага отмены перед новым запросом"""
        self._is_cancelled = False
        self._current_response = None

    def encode_image(self, image_path):
        """Кодирование изображения в Base64"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def format_text_to_html(self, text):
        """Автоматическое форматирование сырого текста от ИИ в красивую книжную верстку"""
        return self.text_formatter.format_to_book_html(text)

    def get_prompt_for_model(self, model_name, target_lang, use_hybrid):
        model_lower = model_name.lower()
        
        if use_hybrid:
            return (
                "Perform high-precision OCR on this image. "
                "Extract all English text exactly as it appears, preserving the exact paragraphs, structure, and spacing. "
                "Return ONLY the extracted text. Do not output any markdown blocks (no ```), translation, or explanations."
            )
        
        if "qwen" in model_lower:
            return f"""You are a precise OCR and translator. Read the image and translate the text into {target_lang}.

CRITICAL RULES:
1. Do NOT write any Chinese characters. Use ONLY English for <original> and {target_lang} for <translation>.
2. You MUST wrap your response in XML tags exactly as shown below. Nothing else is allowed.
3. Do NOT mix languages. English goes in <original>, {target_lang} goes in <translation>.
4. Do NOT add any text outside the tags. No explanations, no commentary.

REQUIRED OUTPUT FORMAT (copy this structure exactly):
<original>
[Extract the exact original English text from the image here, preserving line breaks and paragraph structure]
</original>
<translation>
[Write a natural {target_lang} translation of the original text here]
</translation>"""
        
        elif "minicpm" in model_lower:
            return f"""Task: Read the text on the image and translate it into {target_lang}.
Rules:
- Output ONLY the {target_lang} translation.
- Never output English explanations or conversational filler.
- Strictly follow this format:
<original>
[Original text from image]
</original>
<translation>
[Translation in {target_lang}]
</translation>"""
        
        elif "gpt" in model_lower or "gemini" in model_lower or "claude" in model_lower:
            return f"""You are a professional book translator and advanced OCR engine.
Perform high-fidelity OCR on the image and translate the text into {target_lang}.
Ensure the translation is natural, matches the style of the text, and preserves formatting.

You MUST wrap your response in XML tags exactly as shown below. Do NOT add any text outside the tags.

REQUIRED OUTPUT FORMAT:
<original>
[Extract the exact original text from the image here]
</original>
<translation>
[Write a natural {target_lang} translation here]
</translation>"""
        
        else:
            return f"""Extract all text from this image and translate it into {target_lang}.

You MUST wrap your response in XML tags exactly as shown below. Do NOT add any text outside the tags.

REQUIRED OUTPUT FORMAT:
<original>
[Extract the exact original text from the image here]
</original>
<translation>
[Write a natural {target_lang} translation here]
</translation>"""

    def translate_vision(self, image_path, use_hybrid: Optional[bool] = None,
                         stream_callback: Optional[Callable[[str], None]] = None,
                         ocr_text: str = ""):
        self.reset_cancel()

        base_url = settings.get("llm.base_url", "").rstrip('/')
        model = settings.get("llm.model", "")
        api_key = settings.get("llm.api_key", "")
        
        self.logger.info(f"Отправка Vision-запроса на {base_url} с моделью {model}")
        
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
            return (
                "Ключ API не найден",
                "<h2 style='color:#FF6B6B;'>Ошибка сервиса ИИ</h2>"
                f"<p><b>Сервер:</b> {base_url}</p>"
                "<p><b>Причина:</b> API-ключ не указан. Укажите ключ в настройках.</p>"
            )

        if use_hybrid is None:
            use_hybrid = settings.get("llm.translate_with_standard_engine", False)

        try:
            base64_image = self.encode_image(image_path)
            
            prompt = self.get_prompt_for_model(model, target_lang, use_hybrid)

            api_key_clean = api_key.strip() if api_key else ""
            headers = {"Content-Type": "application/json"}
            if api_key_clean:
                headers["Authorization"] = f"Bearer {api_key_clean}"
            
            img_url = f"data:image/jpeg;base64,{base64_image}"

            payload = {
                "model": model, 
                "messages": [
                    {
                        "role": "user", 
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": img_url}}
                        ]
                    }
                ], 
                "max_completion_tokens": 1024,
                "temperature": 0.2
            }

            if is_local_ollama:
                payload["keep_alive"] = "30m"

            use_stream = stream_callback is not None
            if use_stream:
                payload["stream"] = True

            if self._is_cancelled:
                return "Отменено", "<b>Запрос отменён</b>"

            timeout = 90 if is_local_ollama else 60
            response = requests.post(
                f"{base_url}/chat/completions", 
                headers=headers, 
                json=payload, 
                timeout=timeout,
                stream=use_stream
            )
            self._current_response = response

            if response.status_code != 200:
                try:
                    err_data = response.json()
                    err_msg = err_data.get('error', {}).get('message', '') or str(response.status_code)
                except Exception:
                    err_msg = f"HTTP {response.status_code}"
                err_lower = err_msg.lower()
                if 'max_completion_tokens' in err_lower:
                    self.logger.info("Server rejected max_completion_tokens, retrying with max_tokens")
                    payload.pop("max_completion_tokens", None)
                    payload["max_tokens"] = 1024
                    self._current_response = None
                    response = requests.post(
                        f"{base_url}/chat/completions", 
                        headers=headers, 
                        json=payload, 
                        timeout=timeout,
                        stream=use_stream
                    )
                    self._current_response = response
                    if response.status_code != 200:
                        try:
                            err_data = response.json()
                            err_msg = err_data.get('error', {}).get('message', '') or str(response.status_code)
                        except Exception:
                            err_msg = f"HTTP {response.status_code}"
                        return "Ошибка", (
                            f"<h2 style='color:#FF6B6B;'>Ошибка сервиса ИИ</h2>"
                            f"<p><b>Сервер:</b> {base_url}</p>"
                            f"<p><b>Модель:</b> {model}</p>"
                            f"<p><b>Причина:</b> {err_msg}</p>"
                        )
                elif any(x in err_lower for x in ['does not support image', 'not support image', 'cannot read', 'image input', 'image_url']):
                    return (
                        "Модель не поддерживает изображения",
                        f"<b style='color:orange;'>Модель «{model}» не поддерживает изображения.</b><br>"
                        f"Выберите Vision-модель в настройках (например, gpt-4o-mini, qwen2.5vl, gemini-1.5-flash)."
                    )
                else:
                    return "Ошибка", (
                        f"<h2 style='color:#FF6B6B;'>Ошибка сервиса ИИ</h2>"
                        f"<p><b>Сервер:</b> {base_url}</p>"
                        f"<p><b>Модель:</b> {model}</p>"
                        f"<p><b>Причина:</b> {err_msg}</p>"
                    )

            if use_stream:
                result = self._process_streaming_response(response, use_hybrid, stream_callback, ocr_text)
                self._current_response = None
                return result
            
            res_json = response.json()
            self._current_response = None
            return self._process_standard_response(res_json, use_hybrid, model, ocr_text)

        except Exception as e:
            self._current_response = None
            if self._is_cancelled:
                return "Отменено", "<b>Запрос отменён</b>"
            self.logger.error(f"Error: {e}")
            return "Ошибка связи", (
                f"<h2 style='color:#FF6B6B;'>Ошибка соединения</h2>"
                f"<p><b>Сервер:</b> {base_url}</p>"
                f"<p><b>Модель:</b> {model}</p>"
                f"<p><b>Причина:</b> {str(e)}</p>"
            )
    
    def _process_streaming_response(self, response, use_hybrid: bool, stream_callback: Callable[[str], None], ocr_text: str = ""):
        """Обработка стримингового ответа от LLM"""
        collected_content = []
        
        try:
            for line in response.iter_lines():
                if self._is_cancelled:
                    break
                if not line:
                    continue
                
                line_str = line.decode('utf-8', errors='ignore')
                
                if line_str.startswith('data: '):
                    data_str = line_str[6:]
                    
                    if data_str.strip() == '[DONE]':
                        break
                    
                    try:
                        data = json.loads(data_str)
                        choices = data.get('choices', [])
                        if choices:
                            delta = choices[0].get('delta', {})
                            content_chunk = delta.get('content', '')
                            if content_chunk:
                                collected_content.append(content_chunk)
                                
                                raw_text = ''.join(collected_content)
                                cleaned = self._clean_streaming_text(raw_text)
                                stream_callback(cleaned)
                    except json.JSONDecodeError:
                        continue
            
            full_content = ''.join(collected_content)
            
            if self._is_cancelled:
                return "Отменено", "<b>Запрос отменён</b>"
            
            if not full_content.strip():
                return (
                    "Пустой ответ модели",
                    "<b style='color:orange;'>Модель вернула пустой ответ.</b><br>"
                    "Проверьте, что модель поддерживает изображения и корректно настроена."
                )
            
            clean_content = self._clean_streaming_text(full_content)
            
            if use_hybrid:
                orig_html = self.format_text_to_html(clean_content)
                return orig_html, clean_content
            
            return self._parse_translation_response(full_content, ocr_text)
            
        except Exception as e:
            self.logger.error(f"Stream processing error: {e}")
            if self._is_cancelled:
                return "Отменено", "<b>Запрос отменён</b>"
            return (
                "Ошибка стриминга",
                f"<b style='color:red;'>Ошибка при чтении ответа модели:</b> {str(e)}<br>"
                "Попробуйте другую модель или увеличьте таймаут в настройках."
            )
    
    def _clean_streaming_text(self, text: str) -> str:
        # Remove markdown code fences
        text = re.sub(r'^```[a-zA-Z]*\n?', '', text, flags=re.MULTILINE)
        text = re.sub(r'\n?```$', '', text, flags=re.MULTILINE)
        
        # Remove <original>...</original> block entirely (hidden during streaming)
        text = re.sub(r'<original>.*?</original>', '', text, flags=re.DOTALL | re.IGNORECASE)
        
        # Extract content inside <translation> tags if present
        m_trans = re.search(r'<translation>\s*(.*)', text, re.DOTALL | re.IGNORECASE)
        if m_trans:
            inside = m_trans.group(1)
            # Check if closing tag already arrived
            m_close = re.search(r'\s*</translation>', inside, re.IGNORECASE)
            if m_close:
                text = inside[:m_close.start()].strip()
            else:
                text = inside.strip()
        else:
            # No <translation> tag yet — model might still be in <original> or outputting freely
            # Strip any partial opening tags
            text = re.sub(r'</?original>', '', text, flags=re.IGNORECASE).strip()
            text = re.sub(r'<translation>\s*$', '', text, flags=re.IGNORECASE).strip()
            
            # Legacy: strip ===ORIGINAL=== / ===TRANSLATION=== markers
            text = re.sub(r'(?i)(?:\*+|_+|#|=|\s)*original(?:\*+|_+|#|=|\s)*\n?', '', text)
            text = re.sub(r'(?i)(?:\*+|_+|#|=|\s)*translation(?:\*+|_+|#|=|\s)*\n?', '', text)
            text = re.sub(r'(?i)(?:\*+|_+|#|=|\s)*перевод(?:\*+|_+|#|=|\s)*\n?', '', text)
            text = re.sub(r'(?i)(?:\*+|_+|#|=|\s)*оригинал(?:\*+|_+|#|=|\s)*\n?', '', text)
            text = re.sub(r'={3,}', '', text)
        
        return text.strip()
    
    def _parse_translation_response(self, content: str, ocr_text: str = ""):
        clean = content.strip()
        if clean.startswith("```"):
            clean = re.sub(r'^```[a-zA-Z]*\n', '', clean)
            clean = re.sub(r'\n```$', '', clean)
        clean = clean.strip()
        
        orig_txt = ""
        trans_txt = ""
        
        # STEP 1: XML tags <original>...</original> <translation>...</translation>
        m_orig = re.search(r'<original>\s*(.*?)\s*</original>', clean, re.DOTALL | re.IGNORECASE)
        m_trans = re.search(r'<translation>\s*(.*?)\s*</translation>', clean, re.DOTALL | re.IGNORECASE)
        
        if m_orig and m_trans:
            orig_txt = m_orig.group(1).strip()
            trans_txt = m_trans.group(1).strip()
        elif m_trans:
            trans_txt = m_trans.group(1).strip()
            # Try to get original from text before <translation>
            before = clean[:m_trans.start()].strip()
            before = re.sub(r'</?original>', '', before, flags=re.IGNORECASE).strip()
            orig_txt = before if before else (ocr_text or "")
        elif m_orig:
            orig_txt = m_orig.group(1).strip()
            before = clean[:m_orig.start()].strip()
            after = clean[m_orig.end():].strip()
            trans_txt = after if after else before
        
        # STEP 2: Legacy markers ===ORIGINAL=== / ===TRANSLATION=== / Original: / Translation:
        if not orig_txt or not trans_txt:
            pat_eq_orig = re.compile(r'[*#=*\s]*=+original=+[*#=*\s]*\n?', re.IGNORECASE)
            pat_eq_trans = re.compile(r'[*#=*\s]*=+translation=+[*#=*\s]*\n?', re.IGNORECASE)
            pat_label_orig = re.compile(r'(?:^|\n)\s*(?:Original|Оригинал)\s*:\s*\n?', re.IGNORECASE)
            pat_label_trans = re.compile(r'(?:^|\n)\s*(?:Translation|Перевод)\s*:\s*\n?', re.IGNORECASE)
            
            me_o = pat_eq_orig.search(clean)
            me_t = pat_eq_trans.search(clean)
            ml_o = pat_label_orig.search(clean)
            ml_t = pat_label_trans.search(clean)
            
            m_o = me_o or ml_o
            m_t = me_t or ml_t
            
            if m_o and m_t:
                if m_o.start() < m_t.start():
                    orig_txt = clean[m_o.end():m_t.start()].strip()
                    trans_txt = clean[m_t.end():].strip()
                else:
                    trans_txt = clean[m_t.end():m_o.start()].strip()
                    orig_txt = clean[m_o.end():].strip()
            elif m_t and not orig_txt:
                trans_txt = clean[m_t.end():].strip()
                before = clean[:m_t.start()].strip()
                before = re.sub(r'={3,}', '', before).strip()
                orig_txt = before if before else (ocr_text or "")
            elif m_o and not trans_txt:
                orig_txt = clean[m_o.end():].strip()
                after = clean[m_o.end():].strip()
                before = clean[:m_o.start()].strip()
                trans_txt = after if after else before
        
        # STEP 3: Heuristic — split mixed Latin+Cyrillic text
        if not orig_txt or not trans_txt:
            orig_txt, trans_txt = self._heuristic_language_split(clean)
        
        # Fallbacks
        if not orig_txt:
            orig_txt = ocr_text or "Оригинал доступен в буфере обмена"
        if not trans_txt:
            trans_txt = orig_txt
        
        # Safety: never put original text into translation
        if orig_txt and trans_txt:
            orig_lower = orig_txt.strip().lower()
            trans_lower = trans_txt.strip().lower()
            if orig_lower == trans_lower and re.search(r'[\u0400-\u04FF]', trans_txt):
                pass
            elif orig_lower == trans_lower:
                trans_txt = ""

        if trans_txt:
            trans_txt = self._deduplicate_translation(trans_txt)
        
        orig_html = self.format_text_to_html(orig_txt) if orig_txt else "<i>Оригинал недоступен</i>"
        trans_html = self.format_text_to_html(trans_txt) if trans_txt else "<i>Перевод недоступен</i>"
        
        return orig_html, trans_html
    
    def _heuristic_language_split(self, text: str):
        """Split mixed Latin+Cyrillic text at the language boundary."""
        text = re.sub(r'={3,}', '', text).strip()
        if not text:
            return "", ""
        
        has_latin = bool(re.search(r'[a-zA-Z]{2,}', text))
        has_cyrillic = bool(re.search(r'[\u0400-\u04FF]{2,}', text))
        
        if not (has_latin and has_cyrillic):
            if has_cyrillic:
                return "", text
            else:
                return text, ""
        
        m = re.search(
            r'([a-zA-Z][a-zA-Z0-9\s,;:!?\.\-\']*?)'
            r'[.!?]\s+'
            r'(?=[\u0400-\u04FF])',
            text
        )
        if m:
            orig = text[:m.end(1)].rstrip().rstrip(',;:!?.-').strip()
            trans = text[m.end(1):].lstrip('.!?').strip()
            return orig, trans
        
        m = re.search(
            r'([a-zA-Z][a-zA-Z\s,;:!?\.\-]*?)'
            r'\s+'
            r'(?=[\u0400-\u04FF])',
            text
        )
        if m:
            orig = text[:m.end(1)].strip().rstrip(',;:!?.-').strip()
            trans = text[m.end(1):].strip()
            return orig, trans
        
        m = re.search(
            r'([\u0400-\u04FF][\u0400-\u04FF\u0300-\u036F\s,;:!?\.\-]*?)'
            r'\s+'
            r'(?=[a-zA-Z])',
            text
        )
        if m:
            trans = text[:m.end(1)].strip().rstrip(',;:!?.-').strip()
            orig = text[m.end(1):].strip()
            return orig, trans
        
        return "", text

    @staticmethod
    def _deduplicate_translation(text: str) -> str:
        """Удаление дублирующихся блоков перевода."""
        if not text or not text.strip():
            return text
        paragraphs = re.split(r'\n{2,}', text.strip())
        if len(paragraphs) <= 1:
            return text
        seen = []
        result = []
        for p in paragraphs:
            normalized = re.sub(r'\s+', ' ', p.strip().lower())
            if normalized and normalized not in seen:
                seen.append(normalized)
                result.append(p.strip())
        return '\n\n'.join(result)
    
    def translate_text(self, text: str, stream_callback: Optional[Callable[[str], None]] = None) -> str:
        """Translate plain text via LLM (no image). Returns translated string."""
        self.reset_cancel()

        base_url = settings.get("llm.base_url", "").rstrip('/')
        model = settings.get("llm.model", "")
        api_key = settings.get("llm.api_key", "")

        self.logger.info(f"Отправка text-запроса на {base_url} с моделью {model}")

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
            raise ValueError("API ключ не найден")

        prompt = (
            f"You are a professional literary translator. "
            f"Translate the following text into {target_lang}. "
            f"Preserve the formatting and tone. "
            f"Output ONLY the translated text without explanations, greetings, or markdown code blocks."
        )

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text}
            ],
            "max_tokens": 4000
        }
        if is_local_ollama:
            payload["keep_alive"] = "30m"

        use_stream = stream_callback is not None
        if use_stream:
            payload["stream"] = True

        if self._is_cancelled:
            return ""

        timeout = 90 if is_local_ollama else 60
        response = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=timeout,
            stream=use_stream
        )
        self._current_response = response

        if response.status_code != 200:
            try:
                err_data = response.json()
                err_msg = err_data.get('error', {}).get('message', '') or str(response.status_code)
            except Exception:
                err_msg = f"HTTP {response.status_code}"
            raise RuntimeError(f"Ошибка API ({model}, {base_url}): {err_msg}")

        if use_stream:
            result = self._process_streaming_text_response(response, stream_callback)
            self._current_response = None
            return result

        res_json = response.json()
        self._current_response = None

        if 'choices' in res_json and res_json['choices']:
            content = res_json['choices'][0]['message']['content'].strip()
            content = re.sub(r'^```[a-zA-Z]*\n', '', content)
            content = re.sub(r'\n```$', '', content)
            return content.strip()
        else:
            err_msg = res_json.get('error', {}).get('message', 'Неизвестная ошибка API')
            raise RuntimeError(f"Ошибка API ({model}, {base_url}): {err_msg}")

    def _process_streaming_text_response(self, response, stream_callback: Callable[[str], None]) -> str:
        """Process streaming response for text-only translation."""
        collected_content = []
        try:
            for line in response.iter_lines():
                if self._is_cancelled:
                    break
                if not line:
                    continue
                line_str = line.decode('utf-8', errors='ignore')
                if line_str.startswith('data: '):
                    data_str = line_str[6:]
                    if data_str.strip() == '[DONE]':
                        break
                    try:
                        data = json.loads(data_str)
                        choices = data.get('choices', [])
                        if choices:
                            delta = choices[0].get('delta', {})
                            content_chunk = delta.get('content', '')
                            if content_chunk:
                                collected_content.append(content_chunk)
                                stream_callback(''.join(collected_content))
                    except json.JSONDecodeError:
                        continue

            full_content = ''.join(collected_content).strip()
            if self._is_cancelled:
                return ""
            if not full_content:
                raise RuntimeError("Модель вернула пустой ответ")
            return full_content
        except Exception as e:
            self.logger.error(f"Stream text processing error: {e}")
            if self._is_cancelled:
                return ""
            raise

    def _process_standard_response(self, res_json: dict, use_hybrid: bool, model: str, ocr_text: str = ""):
        """Обработка обычного (не стримингового) ответа"""
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
                return orig_html, clean_content 
            
            return self._parse_translation_response(content, ocr_text)
        else:
            err_msg = res_json.get('error', {}).get('message', 'Неизвестная ошибка API')
            return "Ошибка запроса", f"<b style='color:red;'>Ошибка API:</b> {err_msg}"