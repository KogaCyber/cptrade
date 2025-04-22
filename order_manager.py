from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import time
from typing import Dict, List, Optional, Tuple
from logger import Logger

class OrderManager:
    def __init__(self, driver):
        self.driver = driver
        self.logger = Logger("order_manager")
        self.wait = WebDriverWait(driver, 6)
        self.previous_orders: Dict[str, str] = {}  # order_id -> status
        
    def get_orders(self) -> List[Dict[str, str]]:
        """
        Получает список всех активных ордеров
        
        Returns:
            Список словарей с информацией об ордерах
        """
        orders = []
        try:
            # Ждем появления таблицы ордеров
            order_table = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".order-list table"))
            )
            
            # Получаем все строки с ордерами
            order_rows = order_table.find_elements(By.CSS_SELECTOR, "tr.order-row")
            
            for row in order_rows:
                try:
                    order_id = row.get_attribute("data-order-id")
                    status = row.find_element(By.CSS_SELECTOR, ".order-status").text
                    symbol = row.find_element(By.CSS_SELECTOR, ".order-symbol").text
                    type_ = row.find_element(By.CSS_SELECTOR, ".order-type").text
                    price = row.find_element(By.CSS_SELECTOR, ".order-price").text
                    amount = row.find_element(By.CSS_SELECTOR, ".order-amount").text
                    
                    orders.append({
                        "id": order_id,
                        "status": status,
                        "symbol": symbol,
                        "type": type_,
                        "price": price,
                        "amount": amount
                    })
                except (NoSuchElementException, StaleElementReferenceException) as e:
                    self.logger.warning(f"Ошибка при получении данных ордера: {str(e)}")
                    continue
                    
        except TimeoutException:
            self.logger.warning("Таблица ордеров не найдена")
        except Exception as e:
            self.logger.error("Ошибка при получении списка ордеров", exc_info=e)
            
        return orders
        
    def check_order_updates(self) -> List[Dict[str, str]]:
        """
        Проверяет изменения в статусах ордеров
        
        Returns:
            Список обновленных ордеров
        """
        updated_orders = []
        current_orders = self.get_orders()
        
        for order in current_orders:
            order_id = order["id"]
            current_status = order["status"]
            
            # Если ордер новый или статус изменился
            if (order_id not in self.previous_orders or 
                self.previous_orders[order_id] != current_status):
                updated_orders.append(order)
                self.previous_orders[order_id] = current_status
                
        return updated_orders
        
    def cancel_order(self, order_id: str) -> Tuple[bool, str]:
        """
        Отменяет ордер по ID
        
        Args:
            order_id: ID ордера для отмены
            
        Returns:
            (успех, сообщение)
        """
        try:
            # Находим кнопку отмены для конкретного ордера
            cancel_button = self.driver.find_element(
                By.CSS_SELECTOR, 
                f"tr[data-order-id='{order_id}'] .cancel-order-btn"
            )
            
            # Проверяем, что кнопка кликабельна
            if not cancel_button.is_enabled():
                return False, "Кнопка отмены неактивна"
                
            # Кликаем по кнопке
            cancel_button.click()
            
            # Ждем подтверждения отмены
            confirmation = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".cancel-confirmation"))
            )
            
            # Подтверждаем отмену
            confirm_button = confirmation.find_element(By.CSS_SELECTOR, ".confirm-btn")
            confirm_button.click()
            
            # Ждем обновления статуса
            time.sleep(2)  # Даем время на обновление статуса
            
            return True, "Ордер успешно отменен"
            
        except TimeoutException:
            return False, "Таймаут при попытке отмены ордера"
        except NoSuchElementException:
            return False, "Элементы для отмены ордера не найдены"
        except Exception as e:
            self.logger.error("Ошибка при отмене ордера", exc_info=e)
            return False, f"Ошибка: {str(e)}"
            
    def get_order_details(self, order_id: str) -> Optional[Dict[str, str]]:
        """
        Получает детальную информацию об ордере
        
        Args:
            order_id: ID ордера
            
        Returns:
            Словарь с деталями ордера или None
        """
        try:
            order_row = self.driver.find_element(
                By.CSS_SELECTOR, 
                f"tr[data-order-id='{order_id}']"
            )
            
            return {
                "id": order_id,
                "status": order_row.find_element(By.CSS_SELECTOR, ".order-status").text,
                "symbol": order_row.find_element(By.CSS_SELECTOR, ".order-symbol").text,
                "type": order_row.find_element(By.CSS_SELECTOR, ".order-type").text,
                "price": order_row.find_element(By.CSS_SELECTOR, ".order-price").text,
                "amount": order_row.find_element(By.CSS_SELECTOR, ".order-amount").text,
                "filled": order_row.find_element(By.CSS_SELECTOR, ".order-filled").text,
                "time": order_row.find_element(By.CSS_SELECTOR, ".order-time").text
            }
            
        except NoSuchElementException:
            return None
        except Exception as e:
            self.logger.error("Ошибка при получении деталей ордера", exc_info=e)
            return None 