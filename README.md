# Cây Khỏe AI — Hiểu cây hơn, chăm đúng hơn

Website nhận diện trạng thái cây trồng bằng TensorFlow.js, phân tích ảnh ngay trên trình duyệt. Mô hình hiện hỗ trợ **14 trạng thái trên 5 cây trồng: cam, chanh, lúa, mía, ngô**. Kết quả là gợi ý đối chiếu, không phải chẩn đoán chắc chắn.

Dự án của học sinh Trường THCS Lạc Lương, xã Lạc Lương, tỉnh Phú Thọ — kế thừa đề tài KHKT "AI chẩn đoán bệnh cây trồng" (giải Nhất cấp tỉnh năm học 2025–2026).



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
