
import threading

#TODO: __str__ for Representation|mime_type|size|cached|path . and CBItem|id|hash|num_types|total_size

_bytesymbols = [(1, "B"), (int(1e3), "KB"), (int(1e6), "MB"), (int(1e9), "GB")][::-1]
def _format_bytes(n: int, places: int = 2, symbols=True):
    val, dec, sym = -1, -1, "?"
    for value, symbol in _bytesymbols:
        val, dec, sym = n // value, n % value, symbol
        if val: break #too small
    #
    
    if (places > 0 and dec): return f"{val}.{str(dec)[:places]}{" "+sym if symbols else ""}"
    return f"{val} {sym}" 

class Representation:
    __slots__ = ("mime_type", "data", "size", "cached", "path")
    def __init__(self, mime_type: str, data: bytes, size: int, cached: bool, path: str): #bytes
        self.mime_type = mime_type
        self.data = data
        self.size = size
        self.cached = cached
        self.path = path
    def __str__(self):
        return(f"""Representation|{self.mime_type}|\
{_format_bytes(self.size)}|\
{self.cached and "Cached" or "Uncached"}|\
{self.path and self.path or "No path"}""")

#super-shallow copy of a representation
class Alias(Representation):
    __slots__ = ("ref")
    def __init__(self, mime_type:str, ref: Representation):
        self.ref = ref
        self.mime_type = mime_type
    
    @property
    def data(self): return self.ref.data
    @data.setter
    def data(self, value): self.ref.data = value

    @property
    def size(self): return self.ref.size
    @size.setter
    def size(self, value): self.ref.size = value

    @property
    def cached(self): return self.ref.cached
    @cached.setter
    def cached(self, value): self.ref.cached = value

    @property
    def path(self): return self.ref.path
    @path.setter
    def path(self, value): self.ref.path = value

class CBItem:
    __slots__ = ("id", "timestamp", "hash", "types", "primary_type", "total_size", "pinned", "_ready")
    def __init__(self, id: int, timestamp: float, hash: str, types: list[Representation],
                  primary_type: str, total_size: int, pinned: bool=False):
        self.id = id                        # get from db
        self.timestamp = timestamp
        self.hash = hash
        self.types = types
        self.primary_type = primary_type
        self.total_size = total_size
        self.pinned = pinned
        self._ready = threading.Event()     # cleared = Processing, set = Ready

    def _processing(self) -> bool:
        return not self._ready.is_set()

    def get_cached_size(self) -> bool:
        return sum([i.size for i in self.types if not isinstance(i, Alias) and i.cached])
    
    def __str__(self):
        return f"""CBItem|{self.pinned and "Pinned" or "Unpinned"}|\
{self.id}|{self.timestamp}|{self.hash}|{self.primary_type}|\
{len(self.types)} types|{_format_bytes(self.total_size)}"""