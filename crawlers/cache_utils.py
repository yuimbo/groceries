from functools import lru_cache, wraps
from time import time

def timed_lru_cache(seconds: int, maxsize: int = 128):
    def wrapper_decorator(func):
        func = lru_cache(maxsize=maxsize)(func)
        func.lifetime = seconds
        func.expiration = time() + seconds

        @wraps(func)
        def wrapped_func(*args, **kwargs):
            if time() >= func.expiration:
                func.cache_clear()
                func.expiration = time() + func.lifetime
            return func(*args, **kwargs)

        return wrapped_func
    return wrapper_decorator 