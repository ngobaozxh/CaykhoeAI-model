import base64
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def encoded(path):
    return base64.b64encode(path.read_bytes()).decode('ascii')

def js_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')

def main():
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    model = json.loads((ROOT / 'model/quant/model.json').read_text(encoding='utf-8'))
    embedded = '\n'.join([
        'window.__CKAI_SINGLE_FILE=true;',
        'window.__CKAI_KNOWLEDGE=' + js_json((ROOT / 'dieu_tri.json').read_text(encoding='utf-8')) + ';',
        'window.__CKAI_TOPOLOGY=' + js_json({'modelTopology': model['modelTopology']}) + ';',
        'window.__CKAI_SPECS=' + js_json([w for g in model['weightsManifest'] for w in g['weights']]) + ';',
        'window.__CKAI_BIN_B64="' + encoded(ROOT / 'model/quant/group1-shard1of1.bin') + '";',
        'window.__CKAI_binBuffer=function(){const s=atob(window.__CKAI_BIN_B64),a=new Uint8Array(s.length);for(let i=0;i<s.length;i++)a[i]=s.charCodeAt(i);return a.buffer;};'
    ])
    wasm_paths = {name: 'data:application/wasm;base64,' + encoded(ROOT / 'vendor' / name) for name in ['tfjs-backend-wasm.wasm', 'tfjs-backend-wasm-simd.wasm', 'tfjs-backend-wasm-threaded-simd.wasm']}
    embedded += '\nwindow.__CKAI_WASM_PATHS=' + js_json(wasm_paths) + ';'
    for source in ['vendor/tf.min.js', 'vendor/tf-backend-wasm.min.js', 'vendor/html2pdf.bundle.min.js', 'app.js']:
        code = (ROOT / source).read_text(encoding='utf-8')

        code = re.sub(r'</script', r'<\\/script', code, flags=re.I)
        if source == 'app.js':
            code = embedded + '\n' + code
        marker = '<script src="' + source + '"></script>'
        assert html.count(marker) == 1, source
        html = html.replace(marker, '<script>\n' + code + '\n</script>')
    html = re.sub(r'<link[^>]*rel="manifest"[^>]*>', '', html)

    html = re.sub(r'<link[^>]*rel="preload"[^>]*>\s*', '', html)
    for font in sorted((ROOT / 'fonts').glob('*.woff2')):
        html = html.replace(
            'fonts/' + font.name,
            'data:font/woff2;base64,' + encoded(font),
        )
    assert 'fonts/' not in html, 'a font URL survived inlining'
    assert 'rel="preload"' not in html, 'a preload tag survived'
    for icon in ['img/icon-64.png','img/icon-192.png','img/icon-512.png']:
        html = html.replace(icon, 'data:image/png;base64,' + encoded(ROOT / icon))
    html = html.replace('PWA cần tải đủ dữ liệu trước khi dùng ngoại tuyến.', 'Bản một tệp: mọi dữ liệu đã được nhúng sẵn, không cần mạng.')
    for target in [ROOT / 'dist/cay-khoe-ai-1file.html', ROOT / 'outputs/cay-khoe-ai-1file.html']:
        assert target.parent.exists()
        target.write_text(html, encoding='utf-8')
        print(target, target.stat().st_size, 'bytes')

if __name__ == '__main__':
    main()
