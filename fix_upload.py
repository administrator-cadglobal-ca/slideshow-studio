content = open('app/templates/projects/show.html', encoding='utf-8').read()
content = content.replace(
    '<div id="uploadZone" class="upload-zone" data-project="{{ project.id }}">',
    '<label id="uploadZone" class="upload-zone" data-project="{{ project.id }}" style="cursor:pointer;display:block">'
)
content = content.replace(
    '<input type="file" id="photoInput" multiple accept="image/*" style="display:none">',
    '<input type="file" id="photoInput" multiple accept="image/*" style="position:absolute;width:1px;height:1px;opacity:0">'
)
content = content.replace(
    '  </div>\n  {% if project.photos %}',
    '  </label>\n  {% if project.photos %}'
)
open('app/templates/projects/show.html', 'w', encoding='utf-8').write(content)
print('Fixed')
