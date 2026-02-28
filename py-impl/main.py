import src.storage as storage
from src.classes.models import *
from src.classes.clipboard import Clipboard
import src.config as config

import src.builder as clipwatch
import time
from time import perf_counter_ns as tick

storage.open()
print(storage.fetch())
storage.close()


x = Clipboard()
blame = {}

#demo how to use clipwatch.builder() generator
# 1. get types
# 2. send filtered types
# 3. send priority types
# (...) loop to keep fetching types
def build_snapshot(assert_all_types=False, verifyClipboard=Clipboard(), blame:dict={})->CBItem:
    blame["TOTAL"] = tick()
    blame["INIT"] = tick()
    snapshot: CBItem = None
    builder = clipwatch.builder(assert_all_types=assert_all_types)

    types = next(builder)        #                              --> available types
    filtered_types = [i for i in types if i in config.MIME_TYPES["SUPPORT"]]
    builder.send(filtered_types)                # send(filtered_types) or ALL  --> BuilderState.SEND_PRIMARY
    builder.send(filtered_types[0]) # send(primary_types)          --> BuilderState.READY
    blame["INIT"] = tick() - blame["INIT"]
    blame["TYPES"] = [tick(), {}]
    try:
        cleared = False
        while True:
            diff = tick()
            snapshot, primary_done, added_target = next(builder)
            if not cleared and snapshot in verifyClipboard:
                snapshot = verifyClipboard.getByHash(snapshot.hash)
                break
            else:
                blame["TYPES"][1][added_target] = tick() - diff
                cleared = True
            #if primary_done: break
    except StopIteration as state:
        state: clipwatch.BuilderState = state.value
        if state != clipwatch.BuilderState.SUCCESS: raise RuntimeError( state )
    #
    blame["TYPES"][0] = tick() - blame["TYPES"][0]
    blame["TOTAL"] = tick() - blame["TOTAL"]
    return snapshot

def truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n-1] + "…"
def output_blame(blame, left_align=15,right_align=10):
    print("TIME ELAPSED")
    print("-"*(left_align+right_align+6))
    print(f"{"INIT":>{left_align}} | {blame["INIT"] / 1e6:>{right_align}.3f} ms")
    print(f"{"TYPES":>{left_align}} | {blame["TYPES"][0] / 1e6:>{right_align}.3f} ms")
    print(f"{"TOTAL":>{left_align}} | {blame["TOTAL"] / 1e6:>{right_align}.3f} ms")
    print()
    for k in blame["TYPES"][1]:
        print(f"{truncate(k,left_align):>{left_align}} | {blame["TYPES"][1][k] / 1e6:>{right_align}.3f} ms")
    if not len(blame["TYPES"][1]): print("Fast-lookup, value cached.")
    print("-"*(left_align+right_align+6))
    return


#main loop
while True:
    time.sleep(config.POLL_INTERVAL_MS * 1e-3)
    if not clipwatch.check(): continue
    print("Found new item...")
    new_item = build_snapshot(True, verifyClipboard=x, blame=blame)
    print("Add", new_item)
    x.append(new_item)
    for i in new_item.types:
        print("\t", i)
    print("new state: ", x)
    print()
    output_blame(blame, 25, 8)
    print()