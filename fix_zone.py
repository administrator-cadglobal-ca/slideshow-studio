import re
f = 'app/templates/projects/show.html'
c = open(f, encoding='utf-8').read()

# Replace div with label
c = c.replace(
    '<div id="uploadZone" class="upload-zone" data-project="{{ project.id }}">',
    '<label id="uploadZone" class="upload-zone" data-project="{{ project.id }}" style="cursor:pointer;display:block">'
)
# Make input visible but tiny so label click works
c = c.replace(
    'style="display:none"',
    'style="position:absolute;opacity:0;width:0;height:0"'
)
# Close with label tag
c = c.replace(
    '<input type="file" id="photoInput" multiple accept="image/*" style="position:absolute;opacity:0;width:0;height:0">\n  </div>',
    '<input type="file" id="photoInput" multiple accept="image/*" style="position:absolute;opacity:0;width:0;height:0">\n  </label>'
)
open(f, 'w', encoding='utf-8').write(c)
print('label:', '<label id=\"uploadZone\"' in c)
print('input hidden:', 'opacity:0;width:0;height:0' in c)
