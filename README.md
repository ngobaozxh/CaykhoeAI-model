# Cây Khỏe AI — Hiểu cây hơn, chăm đúng hơn

Website nhận diện trạng thái cây trồng bằng TensorFlow.js, phân tích ảnh ngay trên trình duyệt. Mô hình hiện hỗ trợ **14 trạng thái trên 5 cây trồng: cam, chanh, lúa, mía, ngô**. Kết quả là gợi ý đối chiếu, không phải chẩn đoán chắc chắn.

Dự án của học sinh Trường THCS Lạc Lương, xã Lạc Lương, tỉnh Phú Thọ — kế thừa đề tài KHKT "AI chẩn đoán bệnh cây trồng" (giải Nhất cấp tỉnh năm học 2025–2026).

## Bản nâng cấp hiện tại

- Giao diện nền giấy ấm, xanh rừng làm điểm nhấn duy nhất, tiêu đề serif; bỏ glow tím, gradient neon và hiệu ứng lặp gây rối mắt.
- Chọn cây, kéo thả ảnh, xem trước, chụp ảnh trên thiết bị hỗ trợ; có trạng thái tải, lỗi, thử lại và điều hướng bàn phím.
- Kết quả có ba gợi ý cao nhất, điểm mô hình, cảnh báo khi điểm gần nhau hoặc không khớp cây chọn, dấu hiệu đối chiếu và bước tiếp theo.
- Lịch sử lưu trong IndexedDB; có localStorage dự phòng, hợp nhất theo ID khi bộ nhớ phục hồi. Khởi tạo lịch sử độc lập với AI. Xóa lịch sử yêu cầu xác nhận và chờ giao dịch lưu trữ hoàn tất.
- Xuất PDF tại máy. Ảnh không gửi đến máy chủ; không cần tài khoản.
- TF.js **4.22.0**; ưu tiên **WASM**, dự phòng WebGL rồi CPU. Thư viện và WASM đều có sẵn tại máy; không dùng CDN lúc chạy.

### Hệ thống thiết kế

Quyết định giao diện nằm trong `design-system/cay-khoe-ai/`, không nằm rải rác trong CSS:

- `MASTER.md` — bảng màu, typography, spacing, component spec do skill `ui-ux-pro-max` sinh ra từ truy vấn "Agriculture/Farm Tech".
- Giao diện **cố ý lệch** khỏi `MASTER.md` ở vài chỗ: nền giấy `#F4F6F0` thay vì mint, accent tối hơn để đạt tương phản 4.5:1, và phông chữ tự lưu trữ thay vì import Google Fonts để giữ bảo đảm ngoại tuyến.

Các cổng chống "nhựa AI" đang áp dụng: không màu indigo/tím, không gradient hai điểm trên hero, không emoji làm icon, không thẻ bo góc kèm viền trái màu, không số liệu tự bịa. Điểm mô hình luôn được ghi là *điểm*, không phải tỷ lệ chính xác.

## Dùng không có mạng

### Cách 1: một tệp HTML, phù hợp demo ngoại tuyến

Mở **`dist/cay-khoe-ai-1file.html`** bằng Edge/Chrome. Bản giống hệt để tải/xem nằm tại **`outputs/cay-khoe-ai-1file.html`**.

Tệp nhúng sẵn mô hình, thư viện, WASM, kiến thức và icon; không cần máy chủ hay kết nối mạng để khởi động AI. Dung lượng hiện tại **11,973,789 bytes (~11.42 MiB)**, đã gồm 14 tệp phông chữ nhúng sẵn. Đã kiểm thử mở trực tiếp `file://` với mạng bị tắt ngay từ lần đầu trong hồ sơ trình duyệt mới. Khả năng mở tệp và camera trên trình duyệt điện thoại cần kiểm tra trên thiết bị thực; không coi bài kiểm tra desktop là bảo đảm cho mọi máy.

**Không mở `index.html` trực tiếp để thay cho bản một tệp.** `index.html` dùng tài nguyên riêng, cần chạy qua HTTP/HTTPS.

### Cách 2: website/PWA

Chạy từ thư mục dự án bằng Python trong môi trường phù hợp:

```sh
python -m http.server 8765 --bind 127.0.0.1
```

Mở `http://127.0.0.1:8765/index.html`, đợi cả **"AI sẵn sàng"** và **"Đã lưu đủ để dùng ngoại tuyến"**, rồi mới ngắt mạng. Với website trên internet, dùng HTTPS.

Service worker chỉ hoạt động trong secure context (HTTPS hoặc loopback được trình duyệt chấp nhận); HTTP qua địa chỉ LAN tùy ý không được bảo đảm. PWA tải gói precache nguyên tử và giữ phiên bản tài nguyên nhất quán. Cache hiện tại: `caykhoeai-v8-uint16-wasm-history`. Khi đổi tài nguyên runtime, tăng phiên bản cache rồi build lại bản một tệp.

Bộ nhớ trình duyệt có thể bị người dùng xóa hoặc bị hệ điều hành thu hồi. Yêu cầu persistent storage chỉ là best effort; bản một tệp và PDF là cách giữ bản sao riêng. IndexedDB gắn với origin, không chuyển tự động giữa HTTP, HTTPS và tệp cục bộ.

## Mô hình: những gì đã và chưa chứng minh

| Hạng mục | Kết quả |
| --- | --- |
| Trọng số gốc, giữ nguyên để đối chiếu | 10,509,112 bytes (~10.02 MiB) |
| Trọng số đang triển khai | 5,537,144 bytes (~5.28 MiB) |
| Model JSON + trọng số đang triển khai | 5,623,784 bytes (~5.36 MiB) |
| Giảm dung lượng trọng số | 47.31% |
| So sánh 4 đầu vào tổng hợp | 4/4 giữ top-1; lệch xác suất lớn nhất 0.003521 (~0.352 điểm phần trăm) |
| Kiểm thử trình duyệt mới | 20/20 đạt; không có JS exception |
| Suy luận WASM trên một đầu vào trong lượt kiểm thử | 272 ms; dao động 255–286 ms giữa các lượt, không phải benchmark điện thoại hay toàn bộ luồng ảnh |
| Tensor sau 5 lần suy luận | 278 → 278; không tăng số tensor |
| Kiểm thử cổng dữ liệu huấn luyện | 11/11 đạt; **không chạy training** |
| Phông chữ tự lưu trữ | 14 tệp `.woff2`, 240,384 bytes (subset từ 386,304 bytes); mọi slice `-vi` đủ dấu tiếng Việt |
| Yêu cầu phông chữ ra mạng khi chạy | 0; không có `fonts.googleapis`, `fonts.gstatic`, `@import` |

Bản hiện tại dùng **uint16 để lưu 37 kernel**, giữ float32 cho depthwise, BatchNorm, bias và lớp phân loại cuối. TensorFlow.js giải mã trọng số thành float32. Đây là **nén lưu trữ**, không phải mô hình số nguyên chạy end-to-end, không giảm số phép tính và không chứng minh giảm RAM runtime.

Thử nghiệm uint8 trước đó làm đổi top-1 trên một đầu vào tổng hợp, nên không dùng làm mặc định. Không cắt backbone để giữ head cũ: head cần 1,280 kênh trong khi điểm cắt thử nghiệm chỉ có 160, bắt buộc train head tương thích. `tools/cut_model.py` chủ động chặn cách cắt không hợp lệ.

**Chưa có dữ liệu đánh giá thực địa; chưa chứng minh tăng accuracy/F1, calibration hoặc khả năng nhận diện ảnh ngoài phạm vi. Chưa train model mới.** Điểm softmax, entropy và khoảng cách top-2 chỉ hỗ trợ thận trọng; không bảo đảm loại mọi ảnh không phải cây. Liều thuốc tổng quát trong kho kiến thức chưa được kiểm chứng nên không hiển thị trong kết quả mới. Xác minh bệnh và nhãn sản phẩm với cán bộ kỹ thuật trước khi xử lý.

## Phông chữ

Ba phông tự lưu trữ, không gọi mạng khi chạy:

| Vai trò | Phông | Lý do |
| --- | --- | --- |
| Tiêu đề hero | **Fraunces** (variable, `opsz`, `SOFT`, `WONK`) | Serif mềm, có cá tính; bản italic thật đỡ được dòng thứ hai. |
| Tiêu đề kết quả | **Literata** (variable) | Serif đọc dài; dùng cả trong PDF xuất ra. |
| Giao diện / nội dung | **Be Vietnam Pro** (300–600) | Thiết kế cho tiếng Việt; thay stack hệ thống vốn xuống dấu kém ở cỡ 11–13 px. |

Tạo lại và subset bằng:

```sh
python tools/fetch_fonts.py
```

Script tải `.woff2` gốc, cắt còn đúng tập ký tự ứng dụng dùng, kiểm tra mỗi slice `-vi` có glyph (dưới 30 glyph thì báo lỗi) và ghi `fonts/fonts.css`. Kết quả: 14 tệp, **240,384 bytes** (từ 386,304 bytes). Không tải slice `latin` của Google vì slice `-vi` đã phủ `U+0000-00FF`.

Kiểm tra toàn vẹn dấu tiếng Việt trong từng tệp trước khi phát hành.

## Công cụ thiết kế

Hai skill được cài ở mức người dùng (`~/.workbuddy-ai/skills/`), có ghi chú nguồn và giấy phép tại `~/.workbuddy-ai/skills/INSTALLED-DESIGN-SKILLS.md`:

- **`open-design-craft`** — 12 bộ quy tắc craft từ `nexu-io/open-design` (`craft/`, Apache-2.0). Dùng để chặn "nhựa AI": ngân sách accent tối đa 2 lần hiển thị mỗi màn hình, cổng tương phản, kỷ luật chuyển động.
- **`ui-ux-pro-max`** — từ `nextlevelbuilder/ui-ux-pro-max-skill` (MIT). Sinh `design-system/cay-khoe-ai/MASTER.md`. Gọi bằng Python:

```sh
python ~/.workbuddy-ai/skills/ui-ux-pro-max/scripts/search.py "<query>" --domain ux
```

Lưu ý: `--domain motion` không hợp lệ; hướng dẫn chuyển động nằm ở `--domain gsap`.

**Figma:** MCP Figma đã sẵn sàng trong môi trường này, nhưng cần link file Figma hoặc `fileKey`. Hiện **chưa có file nào được cung cấp**, nên chưa đọc dữ liệu Figma và chưa sinh thiết kế từ Figma. Khi có link, quy trình là: đọc node/token → đối chiếu `MASTER.md` → sửa `index.html` → chạy lại `tools/browser_check.cjs`.

## Build và kiểm thử

Từ thư mục dự án, dùng Python/Node tương thích, ưu tiên runtime cô lập sẵn có:

```sh
# (tuỳ chọn) tạo lại phông chữ đã subset
python tools/fetch_fonts.py
python tools/build_single_file.py
node tools/validate_models.cjs
python tools/verify_quant.py
```

Để chạy kiểm thử UI/offline đầy đủ, khởi động server loopback ở port 8765 như trên, sau đó:

```sh
node tools/browser_check.cjs
```

Bài kiểm thử dùng Edge headless trên Windows và Node có WebSocket tích hợp; hồ sơ mới cho từng lượt, PDF mới có kiểm tra header `%PDF-`. Kiểm tra mở một tệp khi offline, upload/suy luận thật, top-3, cảnh báo, ảnh gần trống, layout 360 px, lịch sử, hợp nhất fallback, xóa lịch sử lúc khởi động, PDF và PWA reload/suy luận offline.

Bằng chứng nằm tại `outputs/browser-validation.json`, `outputs/model-validation.json`, `outputs/training-pipeline-validation.json` và các ảnh preview. Ảnh kiểm thử suy luận là mẫu tổng hợp, không phải dữ liệu chứng minh nhận diện bệnh đúng. Profile, PDF thử và fixture trong `outputs/browser-run-*` / `outputs/training-unit-*` được giữ để kiểm tra; không tự động xóa hàng loạt.

## Chuẩn bị huấn luyện bản nhỏ hơn

`tools/train_candidate.py` chuẩn bị ứng viên **MobileNetV2 alpha=0.5** với head nhỏ, không thay model đang dùng. Cần cung cấp đường dẫn dataset gốc trước khi train. Môi trường hiện tại có Pillow/NumPy nhưng **chưa có TensorFlow**; không cài global. Cài TensorFlow trong một venv riêng tương thích sau khi xác định môi trường huấn luyện. Trọng số ImageNet có thể cần tải một lần trên máy huấn luyện; điều này không ảnh hưởng khả năng offline của bản ứng dụng đã build.

### CSV đầu vào

Cột bắt buộc: **`path,label,split,group`**. Đường dẫn ảnh tương đối với nơi đặt CSV hoặc đường dẫn tuyệt đối. `split` là `train`, `val`, `test`; `group` nhận diện cây/phiên chụp/nguồn để ảnh liên quan không lọt qua nhiều tập. Không chia ngẫu nhiên các ảnh cùng một cây sang cả train và test.

Thứ tự nhãn cố định:

```text
benh_loet_chanh, cam_bi_xi_mu, cam_khoe_manh, chanh_khoe_manh,
chanh_vang_la, lua_bi_nam, lua_binh_thuong, lua_sau_cuon_la,
lua_sau_duc_than, mia_gi_sat, mia_khoe_manh, mia_thoi_do,
ngo_chay_la, ngo_khoe_manh
```

Mỗi nhãn phải có mặt ở cả ba tập; đó chỉ là điều kiện hợp lệ, không chứng minh đủ dữ liệu. Script chặn nhóm trùng split, ảnh trùng pixel dù mã hóa khác, cột CSV trùng, nhãn sai, ảnh quá nhỏ, trên 16 megapixels, ảnh động và ảnh có transparency. Ảnh gần trùng vẫn cần kiểm tra thủ công/nhóm nguồn. Dataset chỉ đọc, không đổi tên hay chỉnh ảnh gốc.

Audit trước, không cần TensorFlow:

```sh
python tools/train_candidate.py --manifest "D:/dataset/manifest.csv" --output "outputs/audit-new" --validate-only
python tools/test_train_candidate.py
```

Các đường dẫn trong ví dụ cần thay bằng vị trí thật. `--output` phải là thư mục **chưa tồn tại**, được giữ riêng để tránh ghi đè/concurrent jobs.

Chỉ train sau khi audit và môi trường đầy đủ:

```sh
python tools/train_candidate.py --manifest "D:/dataset/manifest.csv" --output "outputs/candidate-new" --epochs 25 --fine-epochs 10 --batch 24
```

Input giữ whole-image nearest resize 224×224, RGB/255 và công thức chỉ số tích lũy giống `app.js`. Pillow xử lý EXIF; decoding/color management cần kiểm tra parity ảnh thật trên trình duyệt. Chuẩn hóa ImageNet 2*x−1 nằm trong candidate; augmentation chỉ thuộc wrapper huấn luyện, không lưu trong inference model. Train head trước, fine-tune ít layer cuối với BatchNorm frozen, chọn theo validation loss, dùng test sau khi chọn xong.

Đầu ra: `candidate.keras`, `labels.json`, `dataset_audit.json`, `training_history.json`, `test_predictions.csv`, `evaluation.json` (accuracy, macro F1, recall từng lớp, confusion matrix, ECE). **Pipeline fit và export chưa được chạy.** Chỉ triển khai sau khi so với model gốc trên cùng test độc lập, xuất TF.js thành công, kiểm tra preprocessing/prediction parity, tốc độ thiết bị thật và ảnh ngoài phạm vi.
