from .classes.clipboard import Clipboard, CBItem, _format_bytes
from .config import MAX_ITEMS
from math import log, ceil

def truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n-1] + "…"

#rough solver for birthday problem, determ how much of hash can be truncated at 95% confidence
# b >= 2 * log2(n) + 3.3
truncate_hash = min(32, ceil(2 * log(MAX_ITEMS)/log(2) + 3.3) + 1) # +1 for ellipses

lineformat = lambda count,pin_hash,pin_type,pin_size,unpin_hash,unpin_type,unpin_size,trunc_len: f"||{count:^7}||\
{truncate(pin_hash, truncate_hash):^{truncate_hash+2}}|{truncate(pin_type, trunc_len):^{trunc_len}}|{pin_size:^20}||\
{truncate(unpin_hash,truncate_hash):^{truncate_hash+2}}|{truncate(unpin_type, trunc_len):^{trunc_len}}|{unpin_size:^20}||\
{count:^7}||"

def output_clipboard(c: Clipboard, trunc_len=10) -> str:
    header = lineformat("#", "Pinned", "Type", "Size (C/T)", "Unpinned", "Type", "Size (C/T)", trunc_len)
    outstr = ["-"*len(header), header, "-"*len(header)]

    pinned, unpinned = c.data
    i,j = pinned.front(), unpinned.front()

    bytes_total = 0
    bytes_cached = 0
    for ctr in range(1,1+c.max_items):
        if (i == pinned.tail and j == unpinned.tail): break

        pin_hash,pin_type,pin_size,unpin_hash,unpin_type,unpin_size = "", "", "", "", "", ""
        if i != pinned.tail:
            data: CBItem = i.data
            if data._processing():
                pin_hash, pin_type, pin_size = "...", "...", "..."
            else:
                cached, total = data.get_cached_size(), data.total_size
                bytes_cached += cached
                bytes_total += total
                pin_hash, pin_type, pin_size = data.hash, data.primary_type, f"{_format_bytes(cached, symbols=False)} / {_format_bytes(total)}"
            i = i.next
        if j != unpinned.tail:
            data: CBItem = j.data
            if data._processing():
                unpin_hash, unpin_type, unpin_size = "...", "...", "..."
            else:
                cached, total = data.get_cached_size(), data.total_size
                bytes_cached += cached
                bytes_total += total
                unpin_hash, unpin_type, unpin_size = data.hash, data.primary_type, f"{_format_bytes(cached, symbols=False)} / {_format_bytes(total)}"
            j = j.next
        #
        
        outstr.append( lineformat(ctr, pin_hash, pin_type, pin_size, unpin_hash, unpin_type, unpin_size, trunc_len) )
    #
    outstr.append("-"*len(header))
    outstr.append(f"{len(c.data[0])} Pinned / {len(c.data[1])} Unpinned | {len(c)}/{c.max_items} Total")
    outstr.append(f"{_format_bytes(bytes_cached)} Cached / {_format_bytes(bytes_total)} Total")
    return "\n".join(outstr)

def tryInt(x:any)->int|None:
    try:
        return int(x)
    except:
        return None

def get_range(min=1,max=0,query="", header="", invalid="Invalid input", default=None):
    x = tryInt(input(f"{query} - ").strip() or default)
    while x is None or (x is not default and not (min <= x <= max)):
        x = tryInt( input(f"{invalid + ("" if query else " ")}{query}- ").strip() or default )
    return x

def get_menus(options=[],header="Select an option:",indent="  ", query="", default=None):
    outstr = []
    if header: outstr.append(header)

    for i,v in enumerate(options):
        outstr.append(f"{indent}{i+1} - {v}")

    print("\n".join(outstr))
    return get_range(max=len(options), query=query, default=default)

def msgwait(msg="", wait="Press enter to continue. "):
    if msg: print(msg)
    return input(wait)