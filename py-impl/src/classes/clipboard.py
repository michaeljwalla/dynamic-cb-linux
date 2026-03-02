import threading
from .models import CBItem, Representation, _format_bytes
from .deque import deque, deque_node
from .. import config

class Clipboard:
    __slots__ = ("_hashes", "data", "max_items", "_ready")
    
    def __init__(self, items:deque[CBItem]=None, max_items=config.MAX_ITEMS):
        self.data: list[deque[CBItem]] = [deque(), deque()] # [pinned, unpinned]
        self.max_items = max_items
        self._ready = threading.Event()
        self._ready.set()               # cleared = Processing (item being instantiated), set = Ready

        for n in items or []:
            data: CBItem = n.data
            self.append(data, _nohash=True)
        
        # store the node since that wont change, and improve bringToFront to O(1)
        self._hashes: dict[str, deque_node] = dict()
        for node in self.data[0]:
            if len(self) > max_items: return
            self._hashes[node.data.hash] = node
        for node in self.data[1]:
            if len(self) > max_items: return
            self._hashes[node.data.hash] = node
        return
    
    def __contains__(self, item: CBItem | str):
        return self.getByHash( item.hash if type(item) is CBItem else item ) != None
    
    def __str__(self):
        size = sum([i.data.total_size for i in self.data[0]]) + sum([i.data.total_size for i in self.data[1]])
        return f"Clipboard|{len(self.data[0])}:{len(self.data[1])}|{_format_bytes(size)} Loaded" #Pinned/Unpinned
    
    def __len__(self):
        return len(self.data[0]) + len(self.data[1])

    def _processing(self) -> bool:
        return not self._ready.is_set()

    def append(self, value: CBItem, _nohash=False) -> tuple[bool, CBItem] | None:
        # False, Value -> exists
        if value.hash in self._hashes:
            self.bringToFront(value)
            return False, value                                         

        lost = None
        # False, None -> too many pinned
        if len(self.data[0]) >= self.max_items: return (False, None) 
        elif len(self) == self.max_items:
            lost = self.pop(1)
        #
        self.data[1 - value.pinned].appendLeft(value) # 0 is pinned, 1 is unpinned
        if not _nohash: self._hashes[value.hash] = self.data[1-value.pinned].front() #used in __init__

        # True, any -> success
        return (True, lost)                                             

    def clear(self): #clear the unpinned portion only
        self.data[1].clear()
        self._hashes = {k: v for k, v in self._hashes.items() if v.data.pinned}
        return

    def getByHash(self, hash: str) -> CBItem | None:
        return hash in self._hashes and self._hashes[hash].data or None

    def pop(self, idx: int)-> CBItem | None:
        node = self.data[idx].pop()
        return node and node.data
    
    def bringToFront(self, value: CBItem):
        assert value.hash in self._hashes, "Value not in clipboard. (try append?)"
        #
        section = self.data[1 - value.pinned]
        section.appendLeft( section.remove( self._hashes[value.hash] ) ) #remove the node and append to front
        return
    
    def pin(self, value: CBItem):
        node = value.hash in self._hashes and self._hashes[value.hash] or None
        assert node, "Value not in clipboard. (try append?)"
        if value.pinned:
            self.bringToFront(value)
        else:
            self.data[0].appendLeft( self.data[1].remove( node ) ) #remove from unpinned and append to front
            value.pinned = True
        return
    
    def unpin(self, value: CBItem):
        node = value.hash in self._hashes and self._hashes[value.hash] or None
        assert node, "Value not in clipboard. (try append?)"

        if not value.pinned:
            self.bringToFront(value)
        else:
            self.data[1].appendLeft( self.data[0].remove( node ) ) #remove from unpinned and append to front
            value.pinned = False
        return
    
    def togglepin(self, value: CBItem):
        if value.pinned: self.unpin(value)
        else: self.pin(value)
        return
    
    