import sqlite3
db = sqlite3.connect('instance/slideshow_studio.db')

# Add description column
try:
    db.execute("ALTER TABLE audio_clips ADD COLUMN description TEXT DEFAULT ''")
    print("Added description column")
except Exception as e:
    print("Column may exist:", e)

# Rename existing "Full song" clips to "Song Name - 1" with description "Full Song"
rows = db.execute("SELECT ac.id, af.orig_name FROM audio_clips ac JOIN audio_files af ON ac.song_id = af.id WHERE ac.name = 'Full song'").fetchall()
for clip_id, orig_name in rows:
    base = orig_name.rsplit('.', 1)[0] if '.' in orig_name else orig_name
    db.execute("UPDATE audio_clips SET name=?, description='Full Song' WHERE id=?", (f"{base} - 1", clip_id))
    print(f"Renamed: {orig_name} -> {base} - 1")

db.commit()
db.close()
print('Done')
