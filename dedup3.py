import sqlite3
from pathlib import Path

db = sqlite3.connect('instance/slideshow_studio.db')

# Check actual user_id in DB
user_id = db.execute('SELECT user_id FROM projects WHERE id=?', 
    ('8c199995-ab44-4842-b082-dc622b16b546',)).fetchone()[0]
print('User ID:', user_id)

rows = db.execute('SELECT id, orig_name, filename, project_id FROM photos ORDER BY orig_name, id').fetchall()
print('Total photos in DB:', len(rows))
for r in rows:
    print(r)

seen = {}
to_delete = []
for id, name, filename, project_id in rows:
    if name in seen:
        to_delete.append((id, filename, project_id))
    else:
        seen[name] = id

print(f'\nDuplicates to delete: {len(to_delete)}')
STORAGE = Path('P:/slideshow')
for id, filename, project_id in to_delete:
    src   = STORAGE / 'users' / str(user_id) / 'projects' / project_id / 'source' / filename
    thumb = STORAGE / 'users' / str(user_id) / 'projects' / project_id / 'thumbs' / ('thumb_' + filename)
    print(f'src exists: {src.exists()} -> {src.name}')
    if src.exists():   src.unlink();   print('  deleted source')
    if thumb.exists(): thumb.unlink(); print('  deleted thumb')
    db.execute('DELETE FROM photos WHERE id=?', (id,))

db.commit()
db.close()
print('Done')
