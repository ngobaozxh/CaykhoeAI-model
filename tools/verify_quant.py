import json
import math
import struct
from pathlib import Path
root = Path(__file__).resolve().parent.parent

def read(folder):
    model = json.loads((folder / 'model.json').read_text(encoding='utf-8'))
    b = (folder / model['weightsManifest'][0]['paths'][0]).read_bytes()
    weights, offset = {}, 0
    for s in model['weightsManifest'][0]['weights']:
        n = math.prod(s['shape'])
        q = s.get('quantization')
        if q:
            assert q['dtype'] in ['uint8', 'uint16'] and s['dtype'] == 'float32'
            width = 1 if q['dtype'] == 'uint8' else 2
            raw = struct.unpack_from('<%d%s' % (n, 'B' if width == 1 else 'H'), b, offset)
            values = [v * q['scale'] + q['min'] for v in raw]
            offset += n * width
        else:
            values = struct.unpack_from('<%df' % n, b, offset)
            offset += n * 4
        assert all(math.isfinite(v) for v in values)
        weights[s['name']] = values
    assert offset == len(b)
    return weights

def main():
    a,b = read(root / 'model'), read(root / 'model/quant')
    assert a.keys() == b.keys()
    worst = []
    for name in a:
        assert len(a[name]) == len(b[name])
        worst.append((max(abs(x-y) for x,y in zip(a[name],b[name])), name))
    print(json.dumps({'tensors':len(a), 'largest_weight_errors':sorted(worst,reverse=True)[:8], 'note':'Small weight error does not guarantee accuracy. Field evaluation still required.'},indent=2))

if __name__ == '__main__':
    main()
