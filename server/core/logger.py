import logging
import sys
from functools import wraps
from time import time

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler(sys.stdout) # Явно указываем stdout для Docker
    ]
)

def get_logger(name: str):
    return logging.getLogger(name)

# Декоратор выносим отдельно, так как он не зависит от конкретного экземпляра логгера
def trace_execution(func):
    logger = get_logger(func.__module__) # Берет имя файла как имя логгера
    @wraps(func)
    async def wrapper(*args, **kwargs):
        time_start = time()
        logger.info(f"Функция {func.__name__} начала выполнение")
        try:
            result = await func(*args, **kwargs)
            return result
        except Exception as e:
            logger.error(f"Ошибка в {func.__name__}: {e}")
            raise # ВАЖНО: не глотай ошибку, если не хочешь Exited(0) при падении
        finally:
            logger.info(f"Функция {func.__name__} завершила выполнение за {time() - time_start:.2f}s")
    return wrapper

def count_calls(func):
    logger = get_logger(func.__module__)
    @wraps(func)
    async def wrapper(*args, **kwargs):
        wrapper.calls += 1
        logger.info(f"Функция {func.__name__} была вызвана {wrapper.calls} раз(а)")
        return await func(*args, **kwargs)
    wrapper.calls = 0
    return wrapper 