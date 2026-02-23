from .models import CBItem, Representation
from .deque import deque, deque_node
from . import config

class Clipboard:
    __slots__ = ("_hashes", "data")
    
    def __init__(self, items:deque[CBItem]=[]):
        self.data: list[deque[CBItem]] = [deque(), deque()] # [pinned, unpinned]
        for n in items:
            data: CBItem = n.data
            self.append(data, _nohash=True)
        
        # store the node since that wont change, and improve bringToFront to O(1)
        self._hashes: dict[str, deque_node] = dict()
        for node in self.data[0]:
            self._hashes[node.data.hash] = node
        for node in self.data[1]:
            self._hashes[node.data.hash] = node
    
    def __str__(self):
        return f"Clipboard: {len(self.data[0])}:{len(self.data[1])}" #Pinned/Unpinned
    
    def __len__(self):
        return len(self.data[0]) + len(self.data[1])
    
    def append(self, value: CBItem, _nohash=False) -> tuple[bool, CBItem] | None:
        # False, Value -> exists
        if value.hash in self._hashes: return False, value                                         

        lost = None
        # False, None -> too many pinned
        if len(self.data[0]) >= config.MAX_ITEMS: return (False, None) 
        elif len(self) == config.MAX_ITEMS:
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
        return hash in self._hashes and self._hashes[hash] or None

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

        self.data[0].appendLeft( self.data[1].remove( node ) ) #remove from unpinned and append to front
        value.pinned = True
        return
    
    def unpin(self, value: CBItem):
        node = value.hash in self._hashes and self._hashes[value.hash] or None
        assert node, "Value not in clipboard. (try append?)"

        self.data[1].appendLeft( self.data[0].remove( node ) ) #remove from unpinned and append to front
        value.pinned = False
        return
    