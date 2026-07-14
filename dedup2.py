import sqlite3
from pathlib import Path

db = sqlite3.connect('instance/slideshow_studio.db')

# Get all photos grouped by orig_name, keep lowest id (first uploaded)
rows = db.execute('SELECT id, orig_name, filename, project_id FROM photos ORDER BY orig_name, id').fetchall()

seen = {}
to_delete = []
for id, name, filename, project_id in rows:
    if name in seen:
        to_delete.append((id, filename, project_id))
    else:
        seen[name] = id

print(f'Found {len(to_delete)} duplicates to remove')

STORAGE_ROOT = 'P:/slideshow'
for id, filename, project_id in to_delete:
    # Delete source file
    src = Path(STORAGE_ROOT) / 'users' / '1' / 'projects' / project_id / 'source' / filename
    thumb = Path(STORAGE_ROOT) / 'users' / '1' / 'projects' / project_id / 'thumbs' / ('thumb_' + filename)
    if src.exists():
        src.unlink()
        print(f'Deleted source: {filename}')
    if thumb.exists():
        thumb.unlink()
        print(f'Deleted thumb: thumb_{filename}')
    db.execute('DELETE FROM photos WHERE id=?', (id,))
    print(f'Removed DB record: {id} ({filename})')

db.commit()
db.close()
print('Done')
