
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "dist" / "cay-khoe-ai-1file.html"

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
]

PROBE = """
<script>
(function () {
  var KQ = { ok: false, buoc: 'bat dau', loi: null, backend: null,
             soLop: 0, tong: 0, lop: -1, top3: [], ms: 0 };
  function ghi() {
    var el = document.getElementById('CKAI_PROBE_OUT');
    if (!el) {
      el = document.createElement('div');
      el.id = 'CKAI_PROBE_OUT';
      el.style.display = 'none';
      document.body.appendChild(el);
    }
    el.textContent = 'ZZPROBE' + 'ZZ' + JSON.stringify(KQ) + 'ZZEND' + 'ZZ';
  }
  function cho(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  (async function () {
    try {
      KQ.buoc = 'cho tf';
      if (typeof tf === 'undefined') { KQ.loi = 'khong co tf'; return ghi(); }
      await tf.ready();
      KQ.backend = tf.getBackend();

      KQ.buoc = 'cho mo hinh';
      var n = 240;                       // toi da 120 giay
      while (n-- > 0) {
        if (window.__cayKhoeAI && window.__cayKhoeAI.ready()) break;
        await cho(500);
      }
      if (!(window.__cayKhoeAI && window.__cayKhoeAI.ready())) {
        KQ.loi = 'mo hinh khong san sang sau 120s';
        return ghi();
      }

      KQ.buoc = 'du doan';
      var px = new Float32Array(224 * 224 * 3);
      for (var i = 0; i < px.length; i++) px[i] = 0.5;
      var t0 = performance.now();
      var preds = window.__cayKhoeAI.predictPixels(px);
      KQ.ms = Math.round(performance.now() - t0);

      KQ.soLop = preds.length;
      var tong = 0, mx = -1, mxI = -1;
      for (var j = 0; j < preds.length; j++) {
        tong += preds[j];
        if (preds[j] > mx) { mx = preds[j]; mxI = j; }
      }
      KQ.tong = Math.round(tong * 10000) / 10000;
      KQ.lop = mxI;

      var idx = preds.map(function (v, i) { return i; });
      idx.sort(function (a, b) { return preds[b] - preds[a]; });
      KQ.top3 = idx.slice(0, 3).map(function (i) {
        return [i, Math.round(preds[i] * 10000) / 10000];
      });

      KQ.ok = (preds.length === 14) && Math.abs(tong - 1) < 0.05;
      KQ.buoc = 'xong';
    } catch (e) {
      KQ.loi = String(e && e.message ? e.message : e);
    }
    ghi();
  })();
})();
</script>
"""

def find_browser():
    for c in EDGE_CANDIDATES:
        if Path(c).exists():
            return c
    return None

def main():
    if not TARGET.exists():
        sys.exit(f"Chưa có {TARGET}. Chạy tools/build_single_file.py trước.")

    browser = find_browser()
    if not browser:
        sys.exit("Không tìm thấy Edge/Chrome để kiểm thử.")

    print(f"Trình duyệt : {browser}")
    print(f"Tệp         : {TARGET}  ({TARGET.stat().st_size/1024/1024:.2f} MB)")
    print()

    html = TARGET.read_text(encoding="utf-8")

    injected = html.replace("</body>", PROBE + "</body>", 1)

    tmp = ROOT / "outputs" / "browser-test.html"
    tmp.write_text(injected, encoding="utf-8")

    cmd = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--disable-extensions",
        "--user-data-dir=" + str(ROOT / "outputs" / "edge-test-profile"),
        "--virtual-time-budget=180000",
        "--dump-dom",
        tmp.as_uri(),
    ]
    print("Đang chạy kiểm thử, chờ mô hình nạp và dự đoán (tối đa ~3 phút)…")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=400,
                          encoding="utf-8", errors="replace")

    dom = proc.stdout or ""
    m = re.search(r"ZZPROBEZZ(.*?)ZZENDZZ", dom, re.S)
    if not m:
        print("KHÔNG đọc được kết quả tự kiểm tra.")
        print(f"(DOM nhận được {len(dom)} ký tự)")
        for kw in ("ZZPROBEZZ", "__CKAI_SINGLE_FILE", "Cây Khỏe AI"):
            print(f"  có '{kw}': {kw in dom}")
        print("--- stderr ---")
        print((proc.stderr or "")[:2000])
        sys.exit(1)

    raw = m.group(1)
    raw = (raw.replace("&quot;", '"').replace("&amp;", "&")
              .replace("&lt;", "<").replace("&gt;", ">").replace("&#39;", "'"))
    try:
        res = json.loads(raw)
    except Exception:
        print("Kết quả không phải JSON hợp lệ:")
        print(raw[:1500])
        sys.exit(1)

    print("=== KẾT QUẢ ===")
    print(f"  backend        : {res.get('backend')}")
    print(f"  bước cuối      : {res.get('buoc')}")
    print(f"  số lớp đầu ra  : {res.get('soLop')}")
    print(f"  tổng xác suất  : {res.get('tong')}")
    print(f"  lớp dự đoán    : {res.get('lop')}")
    print(f"  top3           : {res.get('top3')}")
    print(f"  thời gian đoán : {res.get('ms')} ms")
    if res.get("loi"):
        print(f"  LỖI            : {res.get('loi')}")
    print()
    if res.get("ok"):
        print("KẾT LUẬN: Mô hình nạp và dự đoán THÀNH CÔNG ở chế độ một tệp.")
    else:
        print("KẾT LUẬN: THẤT BẠI.")
        sys.exit(1)

    try:
        tmp.unlink()
    except Exception:
        pass

if __name__ == "__main__":
    main()
