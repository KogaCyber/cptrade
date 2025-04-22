import os
import logging
import requests
import time
import threading
from typing import Optional, Union, Callable, Dict, List
from io import BytesIO

class TelegramManager:
    """Менеджер для работы с Telegram API"""
    
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.logger = logging.getLogger(__name__)
        self.command_handlers: Dict[str, Callable] = {}
        self.last_update_id = 0
        self.running = False
        self.poll_thread = None
        
        if not self.bot_token:
            self.logger.warning("⚠️ Отсутствует переменная окружения TELEGRAM_BOT_TOKEN")
        else:
            self.logger.info("✅ Токен бота Telegram настроен")
            
        if not self.chat_id:
            self.logger.warning("⚠️ Отсутствует переменная окружения TELEGRAM_CHAT_ID")
        else:
            self.logger.info(f"✅ ID чата Telegram настроен: {self.chat_id}")
    
    def is_configured(self) -> bool:
        """Проверяет, настроена ли интеграция с Telegram"""
        return bool(self.bot_token)
    
    def register_command(self, command: str, handler: Callable) -> None:
        """
        Регистрирует обработчик команды
        
        Args:
            command: Команда (например, "/start")
            handler: Функция-обработчик
        """
        self.command_handlers[command] = handler
        self.logger.info(f"✅ Зарегистрирован обработчик команды {command}")
    
    def send_message(self, message: str, chat_id: Optional[int] = None) -> bool:
        """
        Отправляет сообщение в Telegram
        
        Args:
            message: Текст сообщения
            chat_id: ID чата для отправки (если None, используется CHAT_ID из .env)
            
        Returns:
            bool: True если сообщение отправлено успешно
        """
        if not self.is_configured():
            self.logger.warning("⚠️ Telegram не настроен")
            return False
        
        try:
            # Используем переданный chat_id или берем из .env
            target_chat_id = chat_id or self.chat_id
            
            # Экранируем специальные символы в сообщении
            escaped_message = message.replace("<", "&lt;").replace(">", "&gt;")
            
            # Отправляем сообщение
            response = requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={
                    "chat_id": target_chat_id,
                    "text": escaped_message,
                    "parse_mode": "HTML"
                }
            )
            
            if response.status_code == 200:
                self.logger.info(f"✅ Сообщение отправлено в чат {target_chat_id}")
                return True
            else:
                self.logger.error(f"❌ Ошибка отправки сообщения в Telegram: {response.status_code}")
                self.logger.error(f"Ответ сервера: {response.text}")
                return False
                
        except Exception as e:
            self.logger.error("❌ Ошибка при отправке сообщения в Telegram", exc_info=e)
            return False
    
    def send_photo(self, photo: Union[bytes, BytesIO], caption: Optional[str] = None, chat_id: Optional[str] = None) -> bool:
        """
        Отправляет фото в Telegram
        
        Args:
            photo: Фото в формате bytes или BytesIO
            caption: Подпись к фото
            chat_id: ID чата для отправки (если None, используется TELEGRAM_CHAT_ID)
        """
        if not self.is_configured():
            self.logger.error("❌ Не настроена интеграция с Telegram")
            return False
            
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
            
            # Преобразуем BytesIO в bytes если необходимо
            if isinstance(photo, BytesIO):
                photo = photo.getvalue()
                
            files = {'photo': ('screenshot.png', photo, 'image/png')}
            data = {"chat_id": chat_id or self.chat_id}
            
            if caption:
                data["caption"] = caption
                
            response = requests.post(url, data=data, files=files)
            
            if response.status_code == 200:
                self.logger.info("✅ Фото успешно отправлено в Telegram")
                return True
            else:
                self.logger.error(f"❌ Ошибка отправки фото в Telegram: {response.status_code}")
                self.logger.error(f"Ответ сервера: {response.text}")
                return False
                
        except Exception as e:
            self.logger.error("❌ Ошибка при отправке фото в Telegram", exc_info=e)
            return False
            
    def start_polling(self) -> None:
        """Запускает процесс получения обновлений от Telegram API"""
        if not self.is_configured():
            self.logger.error("❌ Не настроена интеграция с Telegram")
            return
            
        self.running = True
        self.poll_thread = threading.Thread(target=self._poll_updates)
        self.poll_thread.daemon = True
        self.poll_thread.start()
        self.logger.info("✅ Запущен процесс получения обновлений от Telegram API")
        
    def stop_polling(self) -> None:
        """Останавливает процесс получения обновлений от Telegram API"""
        self.running = False
        if self.poll_thread:
            self.poll_thread.join(timeout=5)
            self.logger.info("✅ Остановлен процесс получения обновлений от Telegram API")
            
    def _poll_updates(self) -> None:
        """Процесс получения обновлений от Telegram API"""
        while self.running:
            try:
                url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
                params = {
                    "offset": self.last_update_id + 1,
                    "timeout": 30
                }
                
                response = requests.get(url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    if data["ok"] and data["result"]:
                        for update in data["result"]:
                            self._handle_update(update)
                            self.last_update_id = update["update_id"]
                else:
                    self.logger.error(f"❌ Ошибка получения обновлений: {response.status_code}")
                    self.logger.error(f"Ответ сервера: {response.text}")
                    
            except Exception as e:
                self.logger.error("❌ Ошибка при получении обновлений", exc_info=e)
                
            time.sleep(1)
            
    def _handle_update(self, update: Dict) -> None:
        """Обрабатывает полученное обновление"""
        if "message" in update and "text" in update["message"]:
            message = update["message"]
            chat_id = str(message["chat"]["id"])
            text = message["text"]
            
            # Если это команда
            if text.startswith("/"):
                command = text.split()[0].lower()
                if command in self.command_handlers:
                    # Создаем копию сообщения с chat_id
                    message_copy = message.copy()
                    message_copy["chat_id"] = chat_id
                    self.command_handlers[command](message_copy)
                else:
                    self.send_message(f"❌ Неизвестная команда: {command}", chat_id)
            else:
                # Если это обычное сообщение
                self.send_message(f"Вы написали: {text}", chat_id)

# Создаем глобальный экземпляр менеджера
telegram_manager = TelegramManager() 