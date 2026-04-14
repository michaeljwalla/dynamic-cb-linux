from threading import get_native_id
from functools import wraps

def trackthread(name: str):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            tid = get_native_id()
            print(f"{name:<25} @ {tid}")

            try:
                return f(*args, **kwargs)
            except Exception:
                print(f"{name + ' FAILED':<25} @ {tid}")
                raise
            finally:
                print(f"{name + ' KILLED':<25} @ {tid}")

        return wrapper
    return decorator