from . import x11api as api
from .classes.models import CBItem, Representation
from . import config 

from typing import Generator
from hashlib import md5
from enum import Enum



class BuilderState(Enum):
    SEND_PRIMARY = -2,
    READY = -1,
    SUCCESS = 0,
    FAIL_TIMEOUT = 1,
    FAIL_LOADPRIMARY = 2,
    FAIL_LOADREGULAR = 3


check = api.check
def _build_snapshot_types(priority:list[str],targets:list[str]) -> Generator[tuple[Representation|BuilderState, bool|str, str], None, BuilderState]:
    count_p = len(priority)
    #
    dupe = set()
    for i,target in enumerate(priority+targets):
        if target in dupe: continue
        else: dupe.add(target)
        #
        if api.check(): return BuilderState.FAIL_TIMEOUT # clipboard changed, stop
        rep = api.fetch_data(target)
        if rep is None:
            yield (BuilderState.FAIL_LOADPRIMARY if i < count_p else BuilderState.FAIL_LOADREGULAR), target, ""
        else:
            yield rep, i+1 < count_p, target # False when all priorities are done
    return BuilderState.SUCCESS

def _hash(data: bytes)->str:
    return md5(data).hexdigest()

# fetches data and hashes
# id is only used in disk storage
def builder(assert_all_types=False) -> Generator[any, list[str], any]:
    global timestamp; timestamp = api.get_timestamp()

    # allow modifying what types to request
    # priority can be used to hash an expected type
    types = api.get_targets()
    types = (yield types) or types
    assert len(types), "At least one datatype is required to snapshot."
    primary = (yield BuilderState.SEND_PRIMARY) or ""
    assert primary in types, "Please enter a primary type (to generate hashes)."

    # init
    snapshot = CBItem(-1, timestamp, "INVALID_STATE", [], primary, 0, False)

    #fetcher's stopiteration states are the same as builders (no purpose of try-catch here)
    fetcher = _build_snapshot_types([primary], types)
    yield BuilderState.READY
    try:
        while True:
            rep, next_is_primary, added_target = next(fetcher)
            if type(rep) == BuilderState:
                failtype = next_is_primary
                assert not assert_all_types, f"Failed to load a {rep == BuilderState.FAIL_LOADREGULAR and "non" or ""}primary type: " + failtype
                assert rep != BuilderState.FAIL_LOADPRIMARY, f"Failed to load a primary type: " + failtype
                continue
            if snapshot.hash == "INVALID_STATE":
                snapshot.hash = _hash(rep.data)                 # try to initialize snapshot quickly (will work after only fetching 1 type)
            
            snapshot.types.append(rep)
            snapshot.total_size += rep.size

            yield snapshot, not next_is_primary, added_target                     # allow early stopping for any reason
        #
    except StopIteration as state:
        return state.value
#