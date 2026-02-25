from . import x11api as api
from .classes.models import CBItem, Representation

from typing import Generator
from hashlib import md5
from enum import Enum

class BuilderState(Enum):
    SUCCESS = 0,
    FAIL_TIMEOUT = 1


timestamp = None
active = True

get_targets = api.get_targets

#just check if 
def check() -> bool: #bool
    global timestamp
    last = timestamp
    timestamp = api.get_timestamp()
    return last != timestamp


def _build_snapshot_types(priority:list[str],targets:list[str]) -> Generator[tuple[Representation, bool], None, int]:
    count_p = len(priority)
    #
    dupe = set()
    for i,target in enumerate(priority+targets):
        if target in dupe: continue
        else: dupe.add(target)
        #
        if check(): return 1 # clipboard changed, stop
        yield api.fetch_data(target), i+1 < count_p # False when all priorities are done
    return 0

def _hash(data: bytes)->str:
    return md5(data).hexdigest()

# fetches data and hashes
# id is only used in disk storage
def builder() -> Generator[any, list[str], any]:
    global timestamp; timestamp = api.get_timestamp()

    # allow modifying what types to request
    # priority can be used to hash an expected type
    types = (yield get_targets()) or []
    assert len(types), "At least one datatype is required to snapshot."
    primary = (yield) or []
    assert len(primary), "At least one primary type should be specified."

    # init
    snapshot = CBItem(-1, timestamp, "INVALID_STATE", [], primary[0], 0, False)

    #fetcher's stopiteration states are the same as builders (no purpose of try-catch here)
    fetcher = _build_snapshot_types(primary, types)
    while True:
        rep, next_is_primary = next(fetcher)
        if snapshot.hash == "INVALID_STATE":
            snapshot.hash = _hash(rep.data)                 # try to initialize snapshot quickly (will work after only fetching 1 type)
        
        snapshot.types.append(rep)
        snapshot.total_size += rep

        yield snapshot, next_is_primary                     # allow early stopping for any reason
    #
#