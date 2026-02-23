# didnt use collections.deque so i could interact w/ nodes better


class deque_node:
    __slots__ = ("data", "prev", "next")
    def __init__(self, data:any = None, prev:"deque_node" = None, next:"deque_node" = None):
        self.data = data
        self.prev: "deque_node" = prev
        self.next: "deque_node" = next

class deque:
    __slots__ = ("head", "tail", "size")
    def __class_getitem__(cls, item): #make subscriptable
        return cls
    def __init__(self):
        self.head: deque_node = deque_node(None, None, deque_node())
        self.tail: deque_node = self.head.next
        self.tail.prev = self.head
        self.size = 0

    def __len__(self):
        return self.size

    def __iter__(self): #i want it to return nodes
        cur = self.head.next
        while cur is not self.tail:
            yield cur
            cur = cur.next
        return
    
    def __str__(self):
        build = "deque(["
        skip = True
        for i in self:
            if skip:
                build += str(i.data) #for comma formattings
                skip = False
                continue
            build += ", " + str(i.data)
        return build + "])"

    
    def append(self, value: any): #righthand side
        node = value
        if type(node) != deque_node:
            node = deque_node(value)
        
        node.next = self.tail
        node.prev = self.tail.prev

        node.prev.next = node
        self.tail.prev = node
        self.size += 1
    
    def appendLeft(self, value: any):
        node = value
        if type(node) != deque_node:
            node = deque_node(value)
        
        node.next = self.head.next
        node.prev = self.head

        node.next.prev = node
        self.head.next = node
        self.size += 1

    def remove(self, node: deque_node) -> deque_node: # trust node exists in deque and is not a sentinel :)
        if not node: return None

        node.prev.next = node.next
        node.next.prev = node.prev
        
        node.next = None
        node.prev = None
        
        self.size -= 1
        return node
    
    def removeOccurrence(self, value: any) -> deque_node | None:
        return self.remove(self.findOccurrence(value))
    def removeOccurrenceCondition(self, cond: any) -> deque_node | None:
        return self.remove(self.findOccurrenceCondition(cond))

    def pop(self) -> deque_node | None:
        if not self.size: return None
        return self.remove(self.tail.prev)
    
    def popLeft(self) -> deque_node | None:
        if not self.size: return None
        return self.remove(self.head.next)
    
    def findOccurrence(self, value: any) -> deque_node | None:
        if not self.size: return None
        for n in self:
            if n.data == value: return n
        return None
    
    def findOccurrenceCondition(self, cond: any) -> deque_node | None:
        if not self.size: return None
        for n in self:
            if cond(n): return n
        return None