from . import x11api as api
from .classes.models import Representation

from typing import Generator

timestamp = None
active = True

#just check if 
def check() -> bool: #bool
    global timestamp
    last = timestamp
    timestamp = api.get_timestamp()
    return last != timestamp

def build_snapshot_types(priority:list[str]=None,targets:list[str]=None) -> Generator[tuple[Representation, bool], None, int]:
    if priority is None: priority = []
    if targets is None: targets = api.get_targets()
    count_p = len(priority)
    #
    dupe = set()
    for i,target in enumerate(priority+targets):
        if target in dupe: continue
        else: dupe.add(target)
        #
        if check(): return 1# clipboard changed, stop
        yield api.fetch_data(target), i < count_p #is priority fetched first
    return 0