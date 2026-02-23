# 1MB, max size each item may be before removing from cache
MEM_THRESHOLD = 2**20
MAX_ITEMS = 50

CACHE_DIRECTORY = "~/.cb_history/"
POLL_INTERVAL_MS = 500

PREVIEW = {
    "MAX_STRLEN": 25,       # truncate (...) after 25 chars
    "MAX_IMGAREA": 256**2   # preview media will shrink to be <= dimensional area
}