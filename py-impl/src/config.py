from pathlib import Path

DEBUG = False


MEM_THRESHOLD_MB = 50
MEM_DUMP_THRESHOLD_MB = MEM_THRESHOLD_MB * 1/3
MAX_ITEMS = 50
MEM_OFFLOAD_THRESHOLD_MB = MEM_DUMP_THRESHOLD_MB / MAX_ITEMS / 2 #once offload is triggered, things over this size go away

CACHE_DIRECTORY = str(Path.home() / ".cb_history")

PREVIEW = {
    "MAX_STRLEN": 25,       # truncate (...) after 25 chars
    "MAX_IMGAREA": 256**2   # preview media will shrink to be <= dimensional area
}

# dict where each element points back to list
# list[-1] is then the preferred reference type
def _generate_aliases(l: list[str], preferred:str=None)->dict[str, list[str]]:
    p = [l + [preferred]]*len(l)
    return dict(zip(l, p))


LEGACY_TEXT_TYPES = {
    "UTF8_STRING",
    "TEXT",
    "STRING",
    "COMPOUND_TEXT",
    #"text/plain"
}
_aliases = {
    "icon":_generate_aliases([ "image/x-icon", "image/x-ico", "image/vnd.microsoft.icon", "application/ico", "image/ico", "image/icon", "text/ico" ]),
    "bmp":_generate_aliases(["image/bmp", "image/x-ms-bmp", "image/x-bmp", "image/x-win-bitmap"], preferred="image/bmp"),
}
MIME_ALIASES = {}
for i in _aliases: MIME_ALIASES |= _aliases[i]

#we dont need this tard type it bugs out half the time
MIME_IGNORE = {}\
    | _aliases["icon"] # icons are usually small and not worth hashing, and often have weird formats that cause issues

#resolve filetypes which dont match their mime type
_txt_overrides = LEGACY_TEXT_TYPES | {"text/plain", "text/plain;charset=utf-8"}
SAVE_TYPE_OVERRIDES = dict(zip(
    [i for i in _txt_overrides],
    ["txt"] * len(_txt_overrides)
))
DEFAULT_SAVE_PATH = "~/Downloads"

OFFLOAD_POLL_INTERVAL = 1.0
OFFLOAD_FETCH_INTERVAL = 0.1
#
WATCH_TIMEOUT = 1
SERVE_POLL_INTERVAL = 0e-3 #ms
WATCH_POLL_INTERVAL = 200e-3
WATCH_POLL_RETRY_INTERVAL = 0e-3