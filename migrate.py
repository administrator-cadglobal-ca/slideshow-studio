import sqlite3
db = sqlite3.connect('instance/slideshow_studio.db')

# Drop old tables to recreate with new schema
db.execute("DROP TABLE IF EXISTS audio_clip_labels")
db.execute("DROP TABLE IF EXISTS audio_clips")
db.execute("DROP TABLE IF EXISTS audio_folders")
db.execute("DROP TABLE IF EXISTS audio_file_folders")
db.execute("DROP TABLE IF EXISTS audio_labels")

db.execute("""CREATE TABLE audio_clips (id INTEGER PRIMARY KEY, song_id INTEGER NOT NULL REFERENCES audio_files(id), name TEXT NOT NULL DEFAULT 'Full song', trim_start TEXT DEFAULT '', trim_end TEXT DEFAULT '', fade_in INTEGER DEFAULT 0, fade_out INTEGER DEFAULT 1, normalize INTEGER DEFAULT 0, created_at TEXT)""")

db.execute("""CREATE TABLE audio_labels (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), project_id INTEGER REFERENCES projects(id), name TEXT NOT NULL, color TEXT DEFAULT '#1e3a52', sort_order INTEGER DEFAULT 0, created_at TEXT)""")

db.execute("""CREATE TABLE audio_clip_labels (clip_id INTEGER NOT NULL REFERENCES audio_clips(id), label_id INTEGER NOT NULL REFERENCES audio_labels(id), PRIMARY KEY (clip_id, label_id))""")

db.execute("INSERT INTO audio_clips (song_id, name, trim_start, trim_end) SELECT id, 'Full song', '', '' FROM audio_files")

db.commit()
db.close()
print('Migration complete')
