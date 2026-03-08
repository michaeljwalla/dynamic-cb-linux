import threading
from pathlib import Path
import re
from tkinter import N

from src import config
from src.classes.models import CBItem, Representation, Alias
from src.classes.clipboard import Clipboard

import json

rwpath: Path = Path.home() / config.CACHE_DIRECTORY / "blobs"
rwpath.mkdir(parents=True, exist_ok=True)

_watcher_thread: threading.Thread | None = None
_watcher_stop:   threading.Event  | None = None

def start(clipboard: Clipboard, offloading=None):
    global _watcher_thread, _watcher_stop

    if _watcher_stop:
        _watcher_stop.set()
    if _watcher_thread and _watcher_thread.is_alive():
        _watcher_thread.join(timeout=1.0)

    stop = threading.Event()
    _watcher_stop = stop
    _watcher_thread = threading.Thread(target=_poll_loop, args=(clipboard, stop, offloading), daemon=True)
    _watcher_thread.start()


def stop():
    global _watcher_stop
    if _watcher_stop:
        _watcher_stop.set()


def sanitize(mime_type: str) -> str:

    sanitized = mime_type.strip()
    sanitized = sanitized.replace("/", "_")
    sanitized = re.sub(r"[;=]", "_", sanitized)
    sanitized = re.sub(r"\s+", "_", sanitized)
    sanitized = re.sub(r"[^\w.\-]", "", sanitized)
    sanitized = re.sub(r"[_.\-]{2,}", "_", sanitized)
    sanitized = sanitized.strip("_.-")

    return sanitized or "SANITIZE_EMPTY"

def offload(item: CBItem, types:list[str]=None, overwrite=False, keepcache=False) -> dict[str, bool]:
    if item._processing(): return {}                                    # not ready
    if types is None: types = [i.mime_type for i in item.types]       # default all
    #
    item._ready.clear()
    #
    dir = rwpath / item.hash
    dir.mkdir(exist_ok=True)

    success = dict(zip(types, [False] * len(types)))
    attempt_writes: list[Representation] = []
    for r in item.types:
        if (r.mime_type not in success): continue
        if isinstance(r, Alias): continue

        attempt_writes.append(r)
    
    for r in attempt_writes:
        file: Path = dir / (sanitize(r.mime_type) + ".bin")
        fail = False
        #
        if not file.exists() or overwrite: #file DNE; file DE but overwrite
            try:
                file.write_bytes(r.data)
            except Exception as e:
                print("WRITE ERR", file, e)
                fail = True
        if fail:
            continue
        elif not keepcache:
            r.data = None
            r.cached = False
            r.path = str(file)
        success[r.mime_type] = True
    
    item._ready.set()
    return success


def load(item: CBItem, types:list[str]=None) -> dict[str, bool]:
    if item._processing(): return {}                                    # not ready
    if types is None: types = [i.mime_type for i in item.types]
    item._ready.clear()
#
    dir = rwpath / item.hash

    success = dict(zip(types, [False] * len(types)))
    if not dir.exists():
        item._ready.set()
        return success
    dir.mkdir(exist_ok=True)

    attempt_reads: list[Representation] = []
    for r in item.types:
        if (r.mime_type not in success): continue
        if isinstance(r, Alias):
            continue
        attempt_reads.append(r)

    for r in attempt_reads:
        file: Path = dir / (sanitize(r.mime_type) + ".bin")
        fail = False
        #
        if not file.exists():
            success[r.mime_type] = r.cached #was already loaded
            continue

        try:
            r.data = file.read_bytes()
        except Exception as e:
            print("READ ERR", file, e)
            fail = True
        if fail:
            continue
        #
        r.cached = True
        r.size = len(r.data)
        r.path = str(file)
        success[r.mime_type] = True
    
    item._ready.set()
    return success

#remove from fs and (opt) load back into memory
def clear(item: CBItem, load=False) -> bool:
    if (item._processing()): return False
    if load: load(item)
    item._ready.clear()

    dir:Path = rwpath / item.hash
    if not dir.exists():
        item._ready.set()
        return True
    toRemove:list[Path] = []
    for f in dir.iterdir():
        if not ((f.name[-4:].lower() == ".bin") and f.is_file()):
            item._ready.set()
            return False #a foreign object exists
        toRemove.append(f)
    #
    for i in toRemove: i.unlink(missing_ok=True)
    dir.rmdir()

    item._ready.set()
    return True

def _json_metadata(item: CBItem) -> str:
    meta = {
        "id": item.id,
        "hash": item.hash,
        "timestamp": item.timestamp,
        "types": [r.mime_type for r in item.types],
        "primary_type": item.primary_type,
        "total_size": item.total_size,
        "pinned": item.pinned
    }
    return json.dumps(meta)

#does NOT make aliases
def _json_to_CBItem(json_str: str, available_types: set[str]) -> CBItem:
    meta = json.loads(json_str)
    types = []
    aliases = {}

    for m in available_types:
        types.append(
            Representation(mime_type=m, data=None, size=0, path="", cached=False)
        )
        if m.lower() in config.MIME_ALIASES:
            aliases[len(types)-1] = config.MIME_ALIASES[m.lower()]
        #
    #
    for ref_idx in aliases:
        for alias in aliases[ref_idx]:
            types.append(
                Alias(mime_type=alias, ref=types[ref_idx])
            )
    
    item = CBItem(
        id=meta["id"],
        hash=meta["hash"],
        timestamp=int(float(meta["timestamp"])),
        types=types,
        primary_type=meta["primary_type"],
        total_size=meta["total_size"],
        pinned=meta["pinned"]
    )
    return item
def persist(item:CBItem) -> bool:
    if item._processing(): return False
#
    dir = rwpath / item.hash
    dir.mkdir(exist_ok=True,parents=True)
    persist_marker = dir / "persist.json"
    persist_marker.write_text( _json_metadata(item) )
    offload(item, keepcache=True)
    return True

def evict(item:CBItem) -> bool:
    if item._processing(): return False
    dir = rwpath / item.hash
    if not dir.exists(): return True
    persist_marker = dir / "persist.json"
    persist_marker.unlink(missing_ok=True)
    return True

unsanitize = lambda s: s.replace("_", "/", 1)
def generate_CBItem(hash:str)->CBItem|None:
    dir:Path = rwpath / hash
    if not dir.exists(): return None
    try:

        available_types = set([ unsanitize(i.name[:-4]) for i in dir.iterdir() if i.name.endswith(".bin")])
        # sanitized mime types such that / is _
        item = _json_to_CBItem((rwpath / hash / "persist.json").read_text(), available_types)
        item._ready.set()
        load(item)
        item.total_size = item.get_cached_size()
    except Exception as e:
        print(f"Error generating CBItem for hash {hash}: {e}")
        return None
    return item

tempEvict = CBItem(id=-1,hash="",timestamp=0, types=[], primary_type="", total_size=0, pinned=False)
tempEvict._ready.set()

def generate_persistent()->list[CBItem]:
    persistent_items = []
    for dir in rwpath.iterdir():
        if dir.is_symlink() or not dir.is_dir(): continue
        persist_marker = dir / "persist.json"
        #
        item = persist_marker.exists() and generate_CBItem(dir.name)
        if not item:
            tempEvict.hash = dir.name
            evict(tempEvict)
            _clear_by_hash(dir.name)
            continue
        persistent_items.append(item)
    
    return persistent_items
        


#trust that hash is not present in clipboard
def _clear_by_hash(hash: str)->bool:
    dir:Path = rwpath / hash
    if not dir.exists(): return True

    toRemove:list[Path] = []
    for f in dir.iterdir():
        if not (f.name == "preview.jpg" or (f.name[-4:].lower() == ".bin") and f.is_file()):
            return False #a foreign object exists
        toRemove.append(f)
    #
    for i in toRemove: i.unlink(missing_ok=True)
    dir.rmdir()

    return True

#remove remnant files
def cleanup_remnants(c: Clipboard, clear_unpinned=False):
    for dir in rwpath.iterdir():
        if dir.is_symlink() or not dir.is_dir(): continue
        dir:Path = dir #type annot bugged
        item = c.getByHash(dir.name)
        if (item and (item.pinned or (not clear_unpinned))): continue #item exists; item is unpinned BUT we arent clearing those
        _clear_by_hash(dir.name)
    return

def _poll_loop(clipboard: Clipboard, stop: threading.Event, offloading=None):
    while not stop.is_set():
        stop.wait(config.OFFLOAD_POLL_INTERVAL)
        if stop.is_set():
            break
        
        if not clipboard._ready.is_set():
            continue
        
        cached_size = 0
        stack = []
        #pinned
        for item in clipboard.data[0]:
            data:CBItem = item.data
            if clipboard.selection is data or data._processing():
                continue
            size = data.get_cached_size()
            if not size or data.total_size < config.MEM_OFFLOAD_THRESHOLD_MB * 1e6: continue
            #
            cached_size += data.total_size
            stack.append(data)

        #unpinned
        for item in clipboard.data[1]:
            data:CBItem = item.data
            if clipboard.selection is data or data._processing():
                continue
            size = data.get_cached_size()
            if not size or data.total_size < config.MEM_OFFLOAD_THRESHOLD_MB * 1e6: continue
            #
            cached_size += data.total_size
            stack.append(data)
        
        if cached_size < config.MEM_THRESHOLD_MB * 1e6:
            continue

        clipboard._ready.clear() #pause clipboard

        proposed = []
        while len(stack) and cached_size > config.MEM_DUMP_THRESHOLD_MB * 1e6:
            item:CBItem = stack.pop()
            if item._processing(): continue
            cached_size -= item.total_size
            proposed.append(item)
        #
        if offloading:
            offloading(True, proposed) #update preview state
        
        for item in proposed:
            offload(item)
            stop.wait(0)
            
        #
        if offloading:
            offloading(False) #update preview state
        
        clipboard._ready.set()

