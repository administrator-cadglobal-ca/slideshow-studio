import sqlite3
db = sqlite3.connect('instance/slideshow_studio.db')
db.execute("""CREATE TABLE IF NOT EXISTS song_folders (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    color TEXT DEFAULT '#1e3a52',
    sort_order INTEGER DEFAULT 0,
    created_at TEXT
)""")
try:
    db.execute("ALTER TABLE audio_files ADD COLUMN song_folder_id INTEGER REFERENCES song_folders(id)")
    print("Added song_folder_id")
except Exception as e:
    print("Column may exist:", e)
db.commit()
db.close()
print('Done')
