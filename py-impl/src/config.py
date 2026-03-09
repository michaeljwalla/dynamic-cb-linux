DEBUG = True


MEM_THRESHOLD_MB = 100
MEM_DUMP_THRESHOLD_MB = MEM_THRESHOLD_MB * 0.8
MAX_ITEMS = 3
MEM_OFFLOAD_THRESHOLD_MB = MEM_DUMP_THRESHOLD_MB / MAX_ITEMS / 2 #once offload is triggered, things over this size go away

CACHE_DIRECTORY = ".cb_history" # in home dir

PREVIEW = {
    "MAX_STRLEN": 25,       # truncate (...) after 25 chars
    "MAX_IMGAREA": 256**2   # preview media will shrink to be <= dimensional area
}

# dict where each element points back to list
def _generate_aliases(l: list[str])->dict[str, list[str]]:
    return dict(zip(l, [l for _ in l]))
# compilation of all aliases currently found

_aliases = {
    "icon":_generate_aliases([ "image/x-icon", "image/x-ico", "image/vnd.microsoft.icon", "application/ico", "image/ico", "image/icon", "text/ico" ]),
    "bmp":_generate_aliases(["image/bmp", "image/x-ms-bmp", "image/x-bmp", "image/x-win-bitmap"]),
}
MIME_ALIASES = {}
for i in _aliases: MIME_ALIASES |= _aliases[i]

#we dont need this tard type it bugs out half the time
MIME_IGNORE = {}\
    | _aliases["icon"] # icons are usually small and not worth hashing, and often have weird formats that cause issues
# MIME_TYPES = {
#     "WILL_HASH": set([
#         'text/plain',
#         'text/plain;charset=utf-8',
#         'text/html',
#         'text/rtf',
#         'UTF8_STRING',  # common legacy

#         # image
#         'image/png',
#         'image/jpeg',
#         'image/webp',
#         'image/tiff',
#         'image/bmp',

#         # files
#         'text/uri-list',

#         # office - microsoft
#         'application/vnd.ms-excel',
#         'application/vnd.ms-word',
#         'application/vnd.ms-powerpoint',

#         # office - open document
#         'application/vnd.oasis.opendocument.text',
#         'application/vnd.oasis.opendocument.spreadsheet',
#         'application/vnd.oasis.opendocument.presentation',
#     ]),
#     "WILL_HASH": { # What it will try to fetch. * means fetch all, anything before will stop early
        
#     }
# }

OFFLOAD_POLL_INTERVAL = 1.0
OFFLOAD_FETCH_INTERVAL = 0.1
#
WATCH_TIMEOUT = 1
SERVE_POLL_INTERVAL = 0e-3 #ms
WATCH_POLL_INTERVAL = 200e-3
WATCH_POLL_RETRY_INTERVAL = 0e-3