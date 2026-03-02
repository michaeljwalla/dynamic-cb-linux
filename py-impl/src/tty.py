from .classes.clipboard import Clipboard, CBItem, _format_bytes
from .config import MAX_ITEMS
from math import log, ceil

def truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n-1] + "…"

#rough solver for birthday problem, determ how much of hash can be truncated at 95% confidence
# b >= 2 * log2(n) + 3.3
truncate_hash = min(32, ceil(2 * log(MAX_ITEMS)/log(2) + 3.3) + 1) # +1 for ellipses

lineformat = lambda count,pin_hash,pin_type,pin_size,unpin_hash,unpin_type,unpin_size,trunc_len: f"||{count:^13}||\
{truncate(pin_hash, truncate_hash):^{truncate_hash+2}}|{truncate(pin_type, trunc_len):^{trunc_len}}|{pin_size:^12}||\
{truncate(unpin_hash,truncate_hash):^{truncate_hash+2}}|{truncate(unpin_type, trunc_len):^{trunc_len}}|{unpin_size:^12}||"

def output_clipboard(c: Clipboard, trunc_len=10) -> str:
    header = lineformat("Clipboard", "Pinned", "Type", "Size", "Unpinned", "Type", "Size", trunc_len)
    outstr = ["-"*len(header), header, "-"*len(header)]

    pinned, unpinned = c.data
    i,j = pinned.front(), unpinned.front()

    for ctr in range(1,1+c.max_items):
        if (i == pinned.tail and j == unpinned.tail): break

        pin_hash,pin_type,pin_size,unpin_hash,unpin_type,unpin_size = "", "", "", "", "", ""
        if i != pinned.tail:
            data: CBItem = i.data
            pin_hash, pin_type, pin_size = data.hash, data.primary_type, _format_bytes(data.total_size)
            i = i.next
        if j != unpinned.tail:
            data: CBItem = j.data
            unpin_hash, unpin_type, unpin_size = data.hash, data.primary_type, _format_bytes(data.total_size)
            j = j.next
        #
        outstr.append( lineformat(ctr, pin_hash, pin_type, pin_size, unpin_hash, unpin_type, unpin_size, trunc_len) )
    #
    outstr.append("-"*len(header))
    outstr.append(f"{len(c.data[0])} Pinned / {len(c.data[1])} Unpinned | {len(c)}/{c.max_items} Total")
    return "\n".join(outstr)

def tryInt(x:any)->int|None:
    try:
        return int(x)
    except:
        return None

def get_range(min=1,max=0,query="", invalid="Invalid input.\n", default=None):
    x = tryInt(input(f"{query} - "))
    while x is None:
        print(invalid)
        x = tryInt( input(f"{query} - ") or default )
    return x

def get_menus(options=[],header="Select an option:",indent="  ", query="", default=None):
    outstr = []
    if header: outstr.append(header)

    for i,v in enumerate(options):
        outstr.append(f"{indent}{i+1} - {v}")

    print("\n".join(outstr))
    return get_range(max=len(options), query=query, default=default)