content = open('app/templates/projects/show.html', encoding='utf-8').read()
print('Current zone tag:', 'label' if '<label id="uploadZone"' in content else 'div')
content = content.replace(
    '<div id="uploadZone" class="upload-zone" data-project="{{ project.id }}">',
    '<label id="uploadZone" class="upload-zone" data-project="{{ project.id }}" style="cursor:pointer;display:block">'
)
content = content.replace(
    '<input type="file" id="photoInput" multiple accept="image/*" style="display:none">',
    '<input type="file" id="photoInput" multiple accept="image/*">'
)
# Find closing </div> of upload zone and replace with </label>
import re
content = re.sub(
    r'(<input type="file" id="photoInput"[^>]*>)\s*\n\s*</div>',
    r'\1\n  </label>',
    content
)
open('app/templates/projects/show.html', 'w', encoding='utf-8').write(content)
print('Done - zone is now:', 'label' if '<label id="uploadZone"' in content else 'div')
