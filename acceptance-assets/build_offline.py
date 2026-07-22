from pathlib import Path
import re
root=Path(__file__).resolve().parent.parent
html=(root/'acceptance.html').read_text(encoding='utf-8')
css=(root/'acceptance-assets/app.css').read_text(encoding='utf-8')
js='\n'.join((root/f'acceptance-assets/app-{i}.js').read_text(encoding='utf-8') for i in range(6))
html=html.replace("script-src 'self'; style-src 'self'", "script-src 'unsafe-inline'; style-src 'unsafe-inline'")
html=html.replace('<link rel="stylesheet" href="acceptance-assets/app.css">', '<style>'+css+'</style>')
html=re.sub(r'<script src="acceptance-assets/app-\d+\.js" defer></script>\n?', '', html)
html=html.replace('</body>', '<script>'+js+'</script>\n</body>')
(root/'AXM_Readiness_Offline.html').write_text(html, encoding='utf-8')
print('built', root/'AXM_Readiness_Offline.html')
