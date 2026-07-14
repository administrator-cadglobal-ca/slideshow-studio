f = open('app/templates/audio/index.html', encoding='utf-8').read()
f = f.replace(".strftime('%b %-d, %Y')", ".strftime('%b %d, %Y')")
open('app/templates/audio/index.html', 'w', encoding='utf-8').write(f)
print('Fixed')
