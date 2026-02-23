class Representation:
    __slots__ = ("mime_type", "data", "size")
    def __init__(self, mime_type, data: bytes, size: int): #bytes
        self.mime_type = mime_type
        self.data = data
        self.size = size

class CBItem:
    __slots__ = ("id", "timestamp", "hash", "types", "primary_type", "total_size")
    def __init__(self, id: str, timestamp: float, hash: str, types: list[Representation],
                  primary_type: str, total_size: int):
        self.id = id
        self.timestamp = timestamp
        self.hash = hash
        self.types = types
        self.primary_type = primary_type
        self.total_size = total_size