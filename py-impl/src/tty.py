from .classes.clipboard import Clipboard, CBItem
def truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n-1] + "…"

def output_clipboard(c: Clipboard, truncate_type=10) -> str:
    header = f"|{"Clipboard":^13}||{"Pinned":^32}|{"":^{truncate_type}}||{"Unpinned":^32}|{"":^{truncate_type}}|"
    outstr = [header, "-"*len(header)]

    i,j = Clipboard.data[0].front(), Clipboard.data[1].front()
    for i in range(Clipboard.max_items):


    return "\n".join(outstr)