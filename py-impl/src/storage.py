from . import config
from .models import Representation, CBItem

import sqlite3
from pathlib import Path
from collections import deque

_db = None

def _assert_loaded(state:bool=True):
    assert state == bool(_db), state and "Database not loaded yet." or "Database already loaded."

def open():
    _assert_loaded(False)
    #
    path = Path.home() / config.CACHE_DIRECTORY
    path.mkdir(parents=True,exist_ok=True)

    global _db; _db = sqlite3.connect(path / "data.db")
    cursor = _db.cursor()

    #setup
    cursor.execute("""CREATE TABLE IF NOT EXISTS ClipboardItems (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp REAL NOT NULL,
        hash TEXT NOT NULL,
        primary_type TEXT NOT NULL,
        total_size INTEGER NOT NULL,
        pinned INTEGER NOT NULL DEFAULT 0
    );""")

    cursor.execute("""CREATE INDEX IF NOT EXISTS idx_clipboard_hash
    ON ClipboardItems(hash);""")

    cursor.execute("""CREATE TABLE IF NOT EXISTS Representations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clipboard_item_id TEXT NOT NULL,
        mime_type TEXT NOT NULL,
        data BLOB NOT NULL,
        size INTEGER NOT NULL,
        FOREIGN KEY (clipboard_item_id)
            REFERENCES ClipboardItems(id)
            ON DELETE CASCADE
    );""") #foreign key section autodeletes related Representations

    _db.commit()
    return

def close():
    _assert_loaded()
    global _db; _db.close()
    _db = None
    return

# return the ClipboardItems _db id
def add(item: CBItem) -> int:
    _assert_loaded()
    with _db:
        cursor = _db.cursor()
        cursor.execute("""
            INSERT INTO ClipboardItems (timestamp, hash, primary_type, total_size, pinned)
            VALUES (?, ?, ?, ?, ?)
        """, (item.timestamp, item.hash, item.primary_type, item.total_size, int(item.pinned)))
        
        item_id = cursor.lastrowid
        
        for rep in item.types:
            cursor.execute("""
                INSERT INTO Representations (clipboard_item_id, mime_type, data, size)
                VALUES (?, ?, ?, ?)
            """, (item_id, rep.mime_type, rep.data, rep.size))
    
    return item_id

#false if attempted to remove pinned/nonexistent id
def remove(item_id: int) -> bool:
    _assert_loaded()
    with _db:
        cursor = _db.cursor()
        cursor.execute("SELECT pinned FROM ClipboardItems WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        if row is None or row[0] == 1:  #ignore
            return False
        #
        cursor.execute("DELETE FROM ClipboardItems WHERE id = ?", (item_id,))
    return True

#false if attempted to modify nonexistent id
def repin(item_id: int, status: bool) -> bool:
    _assert_loaded()
    with _db:
        cursor = _db.cursor()
        cursor.execute("SELECT id FROM ClipboardItems WHERE id = ?", (item_id,))
        if cursor.fetchone() is None:
            return False
        #
        cursor.execute("""
            UPDATE ClipboardItems SET pinned = ? WHERE id = ?
        """, (int(status), item_id))

        return True
    
def fetch() -> deque[CBItem]:
    _assert_loaded()
    cursor = _db.cursor()

    cursor.execute("""
        SELECT id, timestamp, hash, primary_type, total_size, pinned
        FROM ClipboardItems
        ORDER BY timestamp ASC
    """)
    rows = cursor.fetchall()
    
    items = deque()
    for row in rows:
        item_id, timestamp, hash, primary_type, total_size, pinned = row
        
        cursor.execute("""
            SELECT mime_type, data, size
            FROM Representations
            WHERE clipboard_item_id = ?
        """, (item_id,))
        
        representations = [
            Representation(mime_type, data, size)
            for mime_type, data, size in cursor.fetchall()
        ]
        
        items.append(CBItem(
            id=item_id,
            timestamp=timestamp,
            hash=hash,
            types=representations,
            primary_type=primary_type,
            total_size=total_size,
            pinned=bool(pinned)
        ))
    #
    return items