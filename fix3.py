content = open('app/templates/projects/show.html', encoding='utf-8').read()
content = content.replace(
    '<input type="file" id="photoInput" multiple accept="image/*">',
    '<input type="file" id="photoInput" multiple accept="image/*" style="display:none">'
)
open('app/templates/projects/show.html', 'w', encoding='utf-8').write(content)
print('Done')
