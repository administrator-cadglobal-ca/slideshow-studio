import sqlite3
db = sqlite3.connect('instance/slideshow_studio.db')
rows = db.execute('SELECT id, orig_name FROM photos ORDER BY orig_name, id').fetchall()
seen = {}
to_delete = []
for id, name in rows:
    if name in seen:
        to_delete.append(id)
    else:
        seen[name] = id
print('Duplicates to remove:', to_delete)
for id in to_delete:
    db.execute('DELETE FROM photos WHERE id=?', (id,))
db.commit()
db.close()
print('Done')
