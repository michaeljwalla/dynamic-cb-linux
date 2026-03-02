# 1MB, max size each item may be before removing from cache
MEM_THRESHOLD = 2**20
MAX_ITEMS = 50

CACHE_DIRECTORY = ".cb_history" # in home dir
POLL_INTERVAL_MS = 500

PREVIEW = {
    "MAX_STRLEN": 25,       # truncate (...) after 25 chars
    "MAX_IMGAREA": 256**2   # preview media will shrink to be <= dimensional area
}

WATCHER = {
    "POLL_RATE": 0.2 #seconds
}

MIME_TYPES = {
    "SUPPORT": set([
        'text/plain',
        'text/plain;charset=utf-8',
        'text/html',
        'text/rtf',
        'UTF8_STRING',  # common legacy

        # image
        'image/png',
        'image/jpeg',
        'image/webp',
        'image/tiff',
        'image/bmp',

        # files
        'text/uri-list',

        # office - microsoft
        'application/vnd.ms-excel',
        'application/vnd.ms-word',
        'application/vnd.ms-powerpoint',

        # office - open document
        'application/vnd.oasis.opendocument.text',
        'application/vnd.oasis.opendocument.spreadsheet',
        'application/vnd.oasis.opendocument.presentation',
    ]),
    "WILL_HASH": { # What it will try to fetch. * means fetch all, anything before will stop early
        
    }
}

FETCH_TIMEOUT = 1.0