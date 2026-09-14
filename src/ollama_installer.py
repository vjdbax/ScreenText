#!/usr/bin/env python3
import os
import json
import time
import subprocess
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    requests = None
    HAS_REQUESTS = False
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QComboBox, QFrame
from PyQt6.QtCore import Qt, pyqtSignal, QThread

class InstallerThread(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, model_name, action="pull"):
        super().__init__()
        self.model_name = model_name
        self.action = action

    def run(self):
        try:
            if self.action == "pull":
                self.status.emit("Проверка системы...")
                if not self.check_ollama_installed():
                    if not self.install_ollama():
                        return

            if self.action == "pull":
                self.pull_model()
            elif self.action == "delete":
                self.delete_model()

        except Exception as e:
            self.finished.emit(False, f"Ошибка: {str(e)}")

    def check_ollama_installed(self):
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        ollama_path = os.path.join(local_app_data, "Programs", "Ollama", "ollama.exe")
        if os.path.exists(ollama_path):
            return True
        try:
            subprocess.run(["ollama", "--version"], capture_output=True, check=True)
            return True
        except:
            return False

    def install_ollama(self):
        if not HAS_REQUESTS:
            self.finished.emit(False, "Библиотека requests не установлена")
            return False
        try:
            self.status.emit("Скачивание Ollama (~50 МБ)...")
            setup_path = os.path.join(os.environ.get("TEMP", ""), "OllamaSetup.exe")
            response = requests.get("https://ollama.com/download/OllamaSetup.exe", stream=True, timeout=20)
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            with open(setup_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        self.progress.emit(int((downloaded / total_size) * 100))
            
            self.status.emit("Установка Ollama (подтвердите в окне Windows)...")
            self.progress.emit(0) 
            subprocess.Popen([setup_path]).wait()
            self.status.emit("Ожидание запуска службы...")
            time.sleep(5)
            return True
        except Exception as e:
            self.finished.emit(False, f"Ошибка установки Ollama: {str(e)}")
            return False

    def pull_model(self):
        if not HAS_REQUESTS:
            self.finished.emit(False, "Библиотека requests не установлена")
            return
        self.status.emit(f"Запрос на загрузку {self.model_name}...")
        self.progress.emit(0)
        pull_url = "http://localhost:11434/api/pull"
        pull_payload = {"name": self.model_name, "stream": True}
        
        response = requests.post(pull_url, json=pull_payload, stream=True, timeout=None)
        for line in response.iter_lines():
            if line:
                data = json.loads(line.decode('utf-8'))
                msg = data.get('status', '')
                
                if 'total' in data and data['total'] > 0:
                    percent = int((data.get('completed', 0) / data['total']) * 100)
                    self.progress.emit(percent)
                    self.status.emit(f"Загрузка слоев: {percent}%")
                else:
                    self.status.emit(msg)

                if msg == "success":
                    self.progress.emit(100)
                    self.finished.emit(True, f"Модель установлена!")
                    break

    def delete_model(self):
        if not HAS_REQUESTS:
            self.finished.emit(False, "Библиотека requests не установлена")
            return
        self.status.emit(f"Удаление модели {self.model_name}...")
        delete_url = "http://localhost:11434/api/delete"
        payload = {"name": self.model_name}
        try:
            response = requests.delete(delete_url, json=payload, timeout=10)
            if response.status_code == 200:
                self.progress.emit(100)
                self.finished.emit(True, f"Модель успешно удалена с ПК.")
            else:
                self.finished.emit(False, f"Ошибка сервера: {response.status_code}")
        except Exception as e:
            self.finished.emit(False, f"Ошибка при удалении: {str(e)}")

class OllamaInstallerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Мастер управления локальным ИИ")
        self.setFixedSize(520, 420)
        
        # Данные моделей
        self.models_data = [
            {
                "name": "Qwen 2.5 VL (3B) — Оптимально",
                "id": "qwen2.5vl:3b",
                "desc": "<b>Рекомендуется для большинства ПК.</b><br>Отличный баланс скорости и качества. Требует ~4 ГБ видеопамяти. Мгновенно распознает текст и структуру."
            },
            {
                "name": "Qwen 2.5 VL (7B) — Макс. точность",
                "id": "qwen2.5vl:7b",
                "desc": "<b>Самая мощная модель.</b><br>Лучшее качество для мелкого текста и сложных таблиц. Требует ~8 ГБ видеопамяти. Работает медленнее, чем 3B."
            },
            {
                "name": "MiniCPM-V 4.6 — Компактная",
                "id": "openbmb/minicpm-v4.6:latest",
                "desc": "<b>Ультра-эффективная модель.</b><br>Высокое качество при малом размере (~1.5 ГБ). Идеально для ноутбуков и слабых видеокарт."
            },
            {
                "name": "Llava (7B) — Классика",
                "id": "llava",
                "desc": "<b>Стабильная альтернатива.</b><br>Проверенная модель, но может уступать Qwen в точности OCR. Занимает ~4.5 ГБ."
            }
        ]

        self.setStyleSheet("""
            QDialog { background-color: #1E1E1E; border: 2px solid #3C3C3C; border-radius: 8px; }
            QLabel { color: #CCCCCC; font-family: "Segoe UI"; font-size: 12px; border: none;}
            QProgressBar { border: 1px solid #3C3C3C; border-radius: 5px; text-align: center; color: white; background-color: #2D2D2D; height: 18px; }
            QProgressBar::chunk { background-color: #0E639C; border-radius: 4px; }
            QPushButton { background-color: #2D2D2D; color: #CCCCCC; border: 1px solid #3C3C3C; border-radius: 4px; padding: 8px; font-weight: bold; }
            QPushButton:hover { background-color: #3C3C3C; color: #FFFFFF; }
            QComboBox { background-color: #2D2D2D; color: white; border: 1px solid #3C3C3C; padding: 6px; border-radius: 4px; }
            QFrame#desc_box { background-color: #252526; border: 1px solid #3C3C3C; border-radius: 6px; }
        """)
        self.success_state = False
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        self.title_label = QLabel("<b>Управление локальными моделями Ollama</b>")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("font-size: 14px; color: white;")
        layout.addWidget(self.title_label)
        
        layout.addWidget(QLabel("Выберите модель:"))
        
        self.model_selector = QComboBox()
        for model in self.models_data:
            self.model_selector.addItem(model["name"], model["id"])
        self.model_selector.currentIndexChanged.connect(self.update_description)
        layout.addWidget(self.model_selector)
        
        # Блок описания
        self.desc_frame = QFrame()
        self.desc_frame.setObjectName("desc_box")
        desc_layout = QVBoxLayout(self.desc_frame)
        self.desc_label = QLabel("")
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("color: #BBBBBB; font-size: 11px; line-height: 140%;")
        desc_layout.addWidget(self.desc_label)
        layout.addWidget(self.desc_frame)
        
        self.update_description(0)
        
        self.status_label = QLabel("Готов к работе.")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        btns_row = QHBoxLayout()
        self.start_btn = QPushButton("Установить / Обновить")
        self.start_btn.setStyleSheet("background-color: #0E639C; color: white;")
        self.start_btn.clicked.connect(self.start_installation)
        
        self.delete_btn = QPushButton("Удалить модель")
        self.delete_btn.setStyleSheet("QPushButton { color: #FF4D4D; } QPushButton:hover { background-color: #551A1A; }")
        self.delete_btn.clicked.connect(self.start_deletion)
        
        btns_row.addWidget(self.start_btn)
        btns_row.addWidget(self.delete_btn)
        layout.addLayout(btns_row)

        self.close_btn = QPushButton("Закрыть")
        self.close_btn.clicked.connect(self.close_dialog)
        layout.addWidget(self.close_btn)
        
    def update_description(self, index):
        if 0 <= index < len(self.models_data):
            self.desc_label.setText(self.models_data[index]["desc"])

    def set_ui_busy(self, busy):
        self.start_btn.setEnabled(not busy)
        self.delete_btn.setEnabled(not busy)
        self.model_selector.setEnabled(not busy)
        self.close_btn.setEnabled(not busy)

    def start_installation(self):
        self.set_ui_busy(True)
        self.progress_bar.setValue(0)
        model_id = self.model_selector.currentData()
        self.thread = InstallerThread(model_id, action="pull")
        self.thread.progress.connect(self.progress_bar.setValue)
        self.thread.status.connect(self.status_label.setText)
        self.thread.finished.connect(self.on_finished)
        self.thread.start()

    def start_deletion(self):
        self.set_ui_busy(True)
        self.progress_bar.setValue(0)
        model_id = self.model_selector.currentData()
        self.thread = InstallerThread(model_id, action="delete")
        self.thread.progress.connect(self.progress_bar.setValue)
        self.thread.status.connect(self.status_label.setText)
        self.thread.finished.connect(self.on_finished)
        self.thread.start()
        
    def on_finished(self, success, message):
        self.set_ui_busy(False)
        self.success_state = success
        self.status_label.setText(message)
        if success:
            self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            self.status_label.setStyleSheet("color: #FF4D4D; font-weight: bold;")

    def get_selected_model(self): 
        return self.model_selector.currentData()
        
    def close_dialog(self): 
        self.accept() if self.success_state else self.reject()