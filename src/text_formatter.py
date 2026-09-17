#!/usr/bin/env python3
"""
Text formatting and OCR post-processing for ScreenText Helper
"""

import re
from typing import List, Dict, Tuple, Optional


class TextFormatter:
    """Класс для постобработки OCR-результатов и форматирования текста в HTML"""
    
    def __init__(self, font_color: str = "#000000", font_size_p: int = 10, font_size_h1: int = 14):
        self.font_color = font_color
        self.font_size_p = font_size_p
        self.font_size_h1 = font_size_h1
    
    def structure_ocr_results(self, results: List) -> List[Dict]:
        """
        Структурирование сырых результатов OCR в линии текста.
        
        Args:
            results: Список кортежей (bbox, text, confidence) от EasyOCR
            
        Returns:
            Список словарей с ключами: text, height, x0, y0
        """
        if not results:
            return []
        
        blocks = []
        for bbox, text, conf in results:
            if conf > 0.4:
                x0 = min(p[0] for p in bbox)
                x1 = max(p[0] for p in bbox)
                y0 = min(p[1] for p in bbox)
                y1 = max(p[1] for p in bbox)
                blocks.append({
                    'x0': x0, 'x1': x1, 'y0': y0, 'y1': y1,
                    'height': y1 - y0, 'cy': (y0 + y1) / 2, 'text': text
                })
        
        if not blocks:
            return []
        
        blocks.sort(key=lambda b: b['cy'])
        
        lines = []
        for b in blocks:
            matched = False
            for line in lines:
                avg_cy = sum(item['cy'] for item in line) / len(line)
                avg_h = sum(item['height'] for item in line) / len(line)
                if abs(b['cy'] - avg_cy) < avg_h * 0.5:
                    line.append(b)
                    matched = True
                    break
            if not matched:
                lines.append([b])
        
        structured = []
        for l in lines:
            l.sort(key=lambda b: b['x0'])
            structured.append({
                'text': " ".join(b['text'] for b in l).strip(),
                'height': sum(b['height'] for b in l) / len(l),
                'x0': l[0]['x0'],
                'y0': l[0]['y0']
            })
        
        return sorted(structured, key=lambda l: l['y0'])
    
    def extract_paragraphs_from_lines(self, sl: List[Dict]) -> List[str]:
        """
        Извлечение абзацев из структурированных линий текста.
        
        Объединяет разорванные дефисами слова и определяет заголовки по высоте шрифта.
        
        Args:
            sl: Список словарей с ключами: text, height, x0, y0
            
        Returns:
            Список строк-абзацев
        """
        if not sl:
            return []
        
        avg_h = sum([l['height'] for l in sl]) / len(sl) if sl else 20
        
        title = ""
        body = sl
        if len(sl) > 1 and sl[0]['height'] > avg_h * 1.15:
            title = sl[0]['text']
            body = sl[1:]
        
        cleaned = []
        for i, line in enumerate(body):
            text = line['text']
            if text.endswith('-') and i < len(body) - 1:
                line['merge_next'] = True
                line['clean_text'] = text[:-1]
            else:
                line['merge_next'] = False
                line['clean_text'] = text
            cleaned.append(line)
        
        para = []
        cur = []
        if title:
            para.append(title)
        
        for i, line in enumerate(cleaned):
            text = line['clean_text']
            if not cur:
                cur.append(text)
            else:
                if cleaned[i-1].get('merge_next', False):
                    cur[-1] = cur[-1] + text
                else:
                    if cleaned[i-1]['text'].endswith(('.', '!', '?')):
                        para.append(" ".join(cur))
                        cur = [text]
                    else:
                        cur.append(text)
        
        if cur:
            para.append(" ".join(cur))
        
        return [p.replace(" . ", ". ").replace(" , ", ", ").replace(" )", ")").replace("( ", "(").strip() for p in para]
    
    def post_process_text(self, sl: List[Dict]) -> Tuple[str, str]:
        """
        Постобработка OCR-результатов: извлечение абзацев и генерация HTML + Markdown.
        
        Args:
            sl: Список словарей с ключами: text, height, x0, y0
            
        Returns:
            Кортеж (markdown_text, html_text)
        """
        p = self.extract_paragraphs_from_lines(sl)
        if not p:
            return "", ""
        
        avg_h = sum([l['height'] for l in sl]) / len(sl) if sl else 20
        has_t = len(sl) > 1 and sl[0]['height'] > avg_h * 1.15
        
        hl = []
        ml = []
        start = 0
        
        if has_t:
            hl.append(
                f'<h1>{p[0]}</h1>'
            )
            ml.append(f"# {p[0]}\n")
            start = 1
        
        for pr in p[start:]:
            hl.append(
                f'<p>{pr}</p>'
            )
            ml.append(pr)
        
        return "\n\n".join(ml), "".join(hl)
    
    def format_to_book_html(self, text: str, is_title_checker=None) -> str:
        """
        Форматирование текста в чистый адаптивный HTML.
        
        Удаляет технические токены, склеивает разорванные строки,
        убирает лишние пустые строки. Без text-indent и justify.
        """
        if not text.strip():
            return ""
        
        text = self._clean_technical_tokens(text)
        
        raw_paragraphs = re.split(r'\n{2,}', text)
        
        merged = []
        for block in raw_paragraphs:
            lines = block.strip().split('\n')
            if not lines:
                continue
            para_lines = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if para_lines:
                    prev = para_lines[-1]
                    if prev.endswith('-'):
                        para_lines[-1] = prev[:-1] + line
                    elif (not prev.endswith(('.', '!', '?', '»', ')'))
                          and (line[0].islower() or line[0] in (',', 'и', 'а', 'но', 'or', 'and', 'but'))):
                        para_lines[-1] = prev + ' ' + line
                    else:
                        para_lines.append(line)
                else:
                    para_lines.append(line)
            if para_lines:
                merged.append(' '.join(para_lines))
        
        html_parts = []
        for p in merged:
            p = p.strip()
            if not p:
                continue
            is_title = False
            if is_title_checker:
                is_title = is_title_checker(p)
            else:
                is_title = (
                    p.startswith("#")
                    or (len(p) < 40 and not p.endswith(('.', '!', '?', '"', '»', ')', ']')))
                )
            
            if is_title:
                p_title = p.lstrip('#').strip()
                html_parts.append(f'<h1>{p_title}</h1>')
            else:
                html_parts.append(f'<p>{p}</p>')
        
        return "".join(html_parts)
    
    @staticmethod
    def _clean_technical_tokens(text: str) -> str:
        """Удаление служебных токенов моделей и мусора."""
        text = re.sub(r'\b(BOT|THK|Human|Assistant|System)\s*:', '', text)
        text = re.sub(r'[""«»]\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*[""«»]', '', text, flags=re.MULTILINE)
        text = re.sub(r'={3,}', '', text)
        text = re.sub(r'```[a-zA-Z]*\n?', '', text)
        text = re.sub(r'\n?```', '', text)

        lines = text.split('\n')
        cleaned_lines = []
        repeat_count = 0
        last_line = ""
        for line in lines:
            l_str = line.strip()
            if l_str and l_str == last_line:
                repeat_count += 1
                if repeat_count < 2:
                    cleaned_lines.append(line)
            else:
                repeat_count = 0
                last_line = l_str
                cleaned_lines.append(line)
        text = '\n'.join(cleaned_lines)

        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()
    
    def format_translation_html(self, text: str) -> str:
        """
        Форматирование переведенного текста в чистый HTML.
        """
        if not text.strip():
            return ""
        
        text = self._clean_technical_tokens(text)
        
        paragraphs = re.split(r'\n{2,}', text)
        html_lines = []
        
        for p in paragraphs:
            p_clean = p.strip()
            if not p_clean:
                continue
            lines = p_clean.split('\n')
            merged_line = ' '.join(l.strip() for l in lines if l.strip())
            html_lines.append(f'<p>{merged_line}</p>')
        
        return "".join(html_lines)


def create_formatter_from_settings() -> TextFormatter:
    """
    Создание экземпляра TextFormatter с настройками из settings.
    
    Returns:
        TextFormatter с текущими настройками шрифтов
    """
    from settings import settings
    
    font_color = settings.get("font_color", "#000000")
    font_size_p = settings.get("font_size_p", 10)
    font_size_h1 = settings.get("font_size_h1", 14)
    
    return TextFormatter(font_color=font_color, font_size_p=font_size_p, font_size_h1=font_size_h1)
