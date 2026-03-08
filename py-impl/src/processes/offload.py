import threading
from pathlib import Path
import re

from src import config
from src.classes.models import CBItem, Representation
from src.classes.clipboard import Clipboard

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

def offload(item: CBItem, types:list[str]=None, overwrite=False) -> dict[str, bool]:
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
        #
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

#trust that hash is not present in clipboard
def _clear_by_hash(hash: str)->bool:
    dir:Path = rwpath / hash
    if not dir.exists(): return True

    toRemove:list[Path] = []
    for f in dir.iterdir():
        if not ((f.name[-4:].lower() == ".bin") and f.is_file()):
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

