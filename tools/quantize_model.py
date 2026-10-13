import argparse
import copy
import json
import math
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "model" / "quant"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bits', type=int, choices=[8, 16], default=16)
    bits = parser.parse_args().bits
    levels = (1 << bits) - 1
    model = json.loads((ROOT / "model/model.json").read_text(encoding="utf-8"))
    source = (ROOT / "model/group1-shard1of1.bin").read_bytes()
    offset = 0
    result = bytearray()
    weights = []
    count = 0
    for original in model["weightsManifest"][0]["weights"]:
        spec = copy.deepcopy(original)
        assert spec["dtype"] == "float32" and "quantization" not in spec
        n = math.prod(spec["shape"])
        raw = source[offset:offset + 4 * n]
        offset += 4 * n
        if spec["name"].endswith("/kernel") and not spec["name"].startswith("dense_2/"):
            vals = struct.unpack("<%df" % n, raw)
            lo, hi = min(vals), max(vals)
            scale = (hi - lo) / levels if hi > lo else 1.0
            codes = [max(0, min(levels, round((v - lo) / scale))) for v in vals]
            if bits == 8:
                result.extend(codes)
            else:
                result.extend(struct.pack('<%dH' % n, *codes))

            spec["quantization"] = {"dtype": 'uint' + str(bits), "min": lo, "scale": scale}
            count += 1
        else:
            result.extend(raw)
        weights.append(spec)
    assert offset == len(source)
    OUT.mkdir(exist_ok=True)
    (OUT / "group1-shard1of1.bin").write_bytes(result)
    model["weightsManifest"] = [{"paths": ["group1-shard1of1.bin"], "weights": weights}]
    model["convertedBy"] = "Cay Khoe AI: uint" + str(bits) + " kernel storage, float32 sensitive tensors"
    (OUT / "model.json").write_text(json.dumps(model, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    total = len(result) + (OUT / "model.json").stat().st_size
    print(json.dumps({"kernel_tensors_quantized": count, "original_bytes": len(source), "candidate_weight_bytes": len(result), "candidate_package_bytes": total, "reduction_percent": round(100 * (1-len(result)/len(source)), 2)}))

if __name__ == "__main__":
    main()
