import logging
import time
import inspect
from functools import wraps


class Logs:
    def __init__(self, filename_:str = "log_csfloat_api.log"):
        logging.basicConfig(
            filename=filename_,
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
        self.log = logging.getLogger(__name__)

    def log_(self, func):
        # поддержка и sync, и async
        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                try:
                    result = await func(*args, **kwargs)  # ключевое отличие [web:136]
                    if isinstance(result, dict):
                        self.log.info(result.get("for_log"))
                    return result
                except Exception as error:
                    self.log.error(
                        f"Error in {func.__name__}, error has name {error}",
                        exc_info=True,
                    )
                    raise
            return wrapper
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                if isinstance(result, dict):
                    self.log.info(result.get("for_log"))
                return result
            except Exception as error:
                self.log.error(
                    f"Error in {func.__name__}, error has name {error}",
                    exc_info=True,
                )
                raise

        return wrapper


class Helpfull(Logs):
    def __init__(self):
        super().__init__()

    def sey_time(self, func):
        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                start = time.time() 
                result = await func(*args, **kwargs)
                end = time.time()
                self.log.info(f"{func.__name__}: {end - start:.6f}s")
                return result
            return wrapper

        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time() 
            result = func(*args, **kwargs)
            end = time.time()
            self.log.info(f"{func.__name__}: {end - start:.6f}s")
            return result
        return wrapper

    def count_calls(self, func):
        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                wrapper.calls += 1
                result = await func(*args, **kwargs)  # ключевое отличие [web:136]
                self.log.info(f"{func.__name__} called {wrapper.calls} times")
                return result
            wrapper.calls = 0
            return wrapper

        @wraps(func)
        def wrapper(*args, **kwargs):
            wrapper.calls += 1
            result = func(*args, **kwargs)
            self.log.info(f"{func.__name__} called {wrapper.calls} times")
            return result
        wrapper.calls = 0
        return wrapper
    
    def get_status_cod(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            status, where = await func(*args, **kwargs)
            if isinstance(status, int) and status >= 400: 
                self.log.info(f"{where} drop whith status_code {status}")
            return status
        return wrapper
    
    def func_say(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            data, where = func(*args, **kwargs)
            self.log.info(f"{where} func have this data {data}")
            return data
        return wrapper


    