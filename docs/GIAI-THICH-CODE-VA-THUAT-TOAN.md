# Hệ thống điểm danh khuôn mặt cho lớp học SamSung
Hướng dẫn sử dụng và giải thích mã nguồn

Cập nhật ngày 29 tháng 10 năm 2026. Phần 16 bổ sung đầy đủ thí nghiệm SVM và cosine.

Tài liệu này giải thích phiên bản đang có của dự án Facial Recognition Attendance System: từ mở ứng dụng, đăng ký học sinh, chọn buổi học đến nhận diện và lưu điểm danh. Mục tiêu là giúp bạn hiểu chương trình làm gì, vì sao nó làm như vậy và tìm đúng đoạn code khi cần sửa.

Điểm cốt lõi: dự án sử dụng mô hình AI đã được huấn luyện sẵn để chuyển khuôn mặt thành vector số. Khi đăng ký, chương trình lưu vector đại diện cho học sinh. Khi điểm danh, chương trình so vector mới với các vector của lớp đang chọn, sau đó áp dụng quy tắc buổi học để quyết định có ghi nhận hay không. Luồng web không huấn luyện lại InsightFace. Dự án có thí nghiệm huấn luyện SVM riêng trên embedding, trình bày ở phần 16.

Tài liệu được đối chiếu với backend/classroom.py, backend/face_engine.py, backend/app.py, frontend/app.js, start.ps1, các bài kiểm thử và công cụ evaluation. Các ví dụ tên, điểm số và giờ trong tài liệu là minh họa, không phải số liệu đánh giá độ chính xác.

## Cách đọc tài liệu
- Nếu muốn chạy ngay, đọc phần 1 và 2.
- Nếu muốn hiểu AI, đọc phần 3 đến 7 theo thứ tự.
- Nếu muốn giải thích code khi báo cáo, đọc thêm phần 8 đến 12.
- Nếu gặp lỗi hoặc muốn phát triển tiếp, đọc phần 13 đến 15.

Các tiêu đề dùng Heading của Word. Bạn có thể bật View → Navigation Pane để di chuyển giữa các phần. Các tên hàm giữ nguyên như trong mã nguồn để tìm bằng Ctrl + F trong VS Code.

## Những thay đổi đã được đưa vào bản này
Đã bổ sung dashboard, giao diện HUCE và Lớp học SamSung, đăng ký bằng webcam, oval dọc chọn người cần nhận diện khi điểm danh và đăng ký bằng webcam, điểm danh theo buổi, lịch sử theo buổi và tổng hợp theo ngày, xuất CSV có tên buổi và công cụ đánh giá AI chạy riêng. Phần nhân viên cũ đã được gỡ bỏ. Các mô tả “mỗi học sinh chỉ điểm danh một lần trong ngày” không còn áp dụng cho lượt điểm danh mới.

---
# 1 Chạy và sử dụng dự án
## Khởi động trên máy hiện tại
Mở PowerShell tại thư mục dự án và chạy hai lệnh sau. Không cần kích hoạt môi trường ảo trước vì start.ps1 gọi trực tiếp Python của dự án.
```powershell
cd D:\SIC\Facial-Recognition-Attendance-System
powershell -ExecutionPolicy Bypass -File .\start.ps1
```
Sau khi máy chủ khởi động, mở http://127.0.0.1:8000/. Giữ cửa sổ terminal chạy trong lúc dùng ứng dụng. Nhấn Ctrl + C trong terminal để dừng. Nếu giao diện còn giữ mã cũ sau khi cập nhật, nhấn Ctrl + F5 trong trình duyệt.

start.ps1 tìm .venv/Scripts/python.exe, điều chỉnh dòng home trong .venv/pyvenv.cfg về thư mục .python của dự án nếu có, rồi thử import các thư viện chính. Sau đó script chuyển vào backend và chạy Uvicorn với app:app, địa chỉ 127.0.0.1 và cổng 8000. Đây là cấu hình chạy trên chính máy đó; điện thoại hoặc laptop khác không truy cập được bằng địa chỉ 127.0.0.1 của máy họ.

## Thao tác theo đúng thứ tự
1. Vào Lớp học, tạo lớp với tên lớp, môn học và giáo viên.
2. Vào Học sinh, chọn lớp và thêm học sinh với mã duy nhất. Chụp một ảnh bằng webcam hoặc tải từ 1 đến 5 ảnh.
3. Vào Điểm danh, chọn lớp và bấm Tạo buổi học. Nhập tên, ngày và khoảng thời gian trong cùng ngày.
4. Chọn buổi vừa tạo rồi bấm Mở điểm danh. Buổi mới được tạo ở trạng thái đóng.
5. Trong ngày và giờ hợp lệ, bật camera, đặt một khuôn mặt trong oval và bấm Chụp & điểm danh.
6. Kết thúc buổi, bấm Đóng điểm danh. Vào Lịch sử, chọn ngày và buổi để xem hoặc xuất CSV.

Nếu mở buổi 08:00–10:00 thì 08:00 được điểm danh, 10:00 không còn được điểm danh. Mọi kiểm tra dùng giờ Việt Nam UTC+7 tại máy chủ. Không hỗ trợ một buổi kéo dài qua nửa đêm.

## Những màn hình hiện có
| Màn hình | Mục đích |
| Tổng quan | Số lớp, số học sinh, người đã có mặt trong ngày, xu hướng 7 ngày và thống kê từng lớp |
| Điểm danh | Chọn buổi, mở hoặc đóng buổi, dùng webcam ghi nhận học sinh |
| Học sinh | Xem danh sách và tạo hồ sơ khuôn mặt |
| Lớp học | Tạo lớp và chuyển sang danh sách học sinh của lớp |
| Lịch sử điểm danh | Chọn ngày, xem từng buổi hoặc tổng hợp ngày và tải CSV |

---
# 2 Kiến trúc và đường đi của dữ liệu
## Ba thành phần chính
Frontend là phần chạy trong trình duyệt: HTML tạo bố cục, CSS trình bày, JavaScript điều khiển camera, form và gọi API. Frontend không tự chạy mô hình nhận diện.

Backend là chương trình Python dùng FastAPI. Nó kiểm tra dữ liệu, điều khiển model, so khớp khuôn mặt và đọc ghi SQLite. Uvicorn là tiến trình phục vụ HTTP để trình duyệt có thể gọi FastAPI.

SQLite là database nằm trong file backend/classroom.db. Đây là nơi lưu lớp, học sinh, vector khuôn mặt, buổi học và kết quả điểm danh. Tắt máy chủ không làm mất dữ liệu đã ghi thành công.

```text
Webcam → Trình duyệt chụp JPEG → API FastAPI
                                 ↓
                      Kiểm tra lớp và buổi học
                                 ↓
                    Phát hiện mặt → lọc theo oval
                                 ↓
                    Trích vector → so với lớp
                                 ↓
                     SQLite ghi điểm danh
                                 ↓
                  JSON trả về → giao diện cập nhật
```

## Ví dụ một yêu cầu thực tế
Khi bấm Chụp & điểm danh, JavaScript tạo FormData chứa trường image rồi gửi POST đến /api/classes/2/recognize?session_id=5. Số 2 là ID lớp, số 5 là ID buổi, không phải số người xuất hiện trong ảnh. Backend kiểm tra buổi 5 thuộc lớp 2 trước khi chạy AI.

Nếu nhận ra học sinh, backend trả JSON chứa status, student, time, similarity, session_id và session_name. Frontend dùng status để hiển thị kết quả rồi tải lại danh sách. Chính bản ghi trong database là căn cứ “Có mặt”, không phải việc vòng oval chuyển màu hoặc việc camera đang bật.

## AI và quy tắc phần mềm là hai phần khác nhau
AI phát hiện vị trí mặt và tạo vector biểu diễn. Những việc như kiểm tra oval, chọn lớp, giới hạn giờ, ngăn điểm danh trùng và tính tỷ lệ có mặt là thuật toán hoặc quy tắc nghiệp vụ do code thông thường thực hiện. Một kết quả nhận diện đúng vẫn có thể không được ghi nếu buổi đã đóng.

Ứng dụng xử lý một ảnh khi bạn bấm chụp. Camera hiển thị video liên tục nhưng backend không tự nhận diện mọi khung hình trong video. Điều này giúp tránh chạy AI liên tục khi chưa cần điểm danh.

---
# 3 AI đang dùng và ý nghĩa của việc train
## Mô hình được nạp ở đâu
backend/face_engine.py khởi tạo một đối tượng FaceAnalysis dùng chung, đặt thư mục model là .insightface và chọn CPUExecutionProvider. prepare(ctx_id=-1, det_size=(640, 640)) cấu hình chạy trên CPU và kích thước xử lý của bộ phát hiện.

Code không chỉ định name của gói model. Thư viện InsightFace đang cài có giá trị mặc định buffalo_l và dự án hiện có gói đó. Vì vậy mô tả này gắn với môi trường hiện tại; nếu đổi thư viện hoặc model, cần kiểm tra lại mặc định.

Trong .insightface/models/buffalo_l có det_10g.onnx cho phát hiện mặt và w600k_r50.onnx cho nhận diện, cùng 1k3d68.onnx, 2d106det.onnx, genderage.onnx. Luồng điểm danh gọi trực tiếp det_model.detect và models["recognition"].get; không gọi các model tuổi, giới tính hay landmark phụ để quyết định điểm danh.

## Hai nhiệm vụ khác nhau
Phát hiện khuôn mặt trả lời “Trong ảnh có mặt ở đâu?”. Đầu ra gồm khung bao mặt, điểm tin cậy phát hiện và các mốc mặt. Nó chưa biết người đó là học sinh nào.

Nhận diện khuôn mặt trả lời “Khuôn mặt này giống hồ sơ nào?”. Model recognition chuyển ảnh mặt đã căn chỉnh thành embedding, rồi chương trình so embedding với dữ liệu đăng ký. Tên học sinh đến từ database, không phải model tự phát ra tên.

## Đăng ký dữ liệu không phải huấn luyện
Huấn luyện mô hình là dùng dữ liệu cùng hàm mất mát để cập nhật trọng số qua tối ưu hóa. Fine tuning cũng làm thay đổi trọng số từ một mô hình có sẵn. Luồng web không cập nhật trọng số ONNX. Thí nghiệm riêng dùng LinearSVC.fit để học trọng số bộ phân loại và lưu mô hình joblib; xem phần 16.

Đăng ký ở đây là chạy suy luận trên ảnh, lấy vector rồi ghi vào students.embedding. Thêm một học sinh làm thay đổi danh sách vector cần so sánh, không làm thay đổi các file ONNX. Nếu xóa database nhưng giữ model, model vẫn phát hiện và tạo vector được, song không còn hồ sơ học sinh để gán tên.

## Dự án có phải dự án AI không
Có, vì chức năng cốt lõi dựa vào suy luận của mô hình học sâu. Cách mô tả đúng là “ứng dụng AI sử dụng mô hình pretrained để nhận diện khuôn mặt và quản lý điểm danh”. Không nên nói “đã tự train mô hình bằng dữ liệu lớp” khi code chưa làm việc đó. Điểm đóng góp hiện tại nằm ở tích hợp model, xử lý ảnh, chọn vùng mặt, so khớp, quản lý buổi và xây dựng ứng dụng.

---
# 4 Thuật toán xử lý ảnh và chọn mặt trong oval
## Từ video đến ảnh gửi lên
Video có thể có tỷ lệ khác khung hiển thị. CSS object-fit: cover khiến một phần mép ảnh bị cắt. Hàm attendanceCrop tính vùng cắt ở giữa ảnh gốc để canvas gửi đúng vùng người dùng đang nhìn thấy, thay vì gửi cả video rồi làm lệch vị trí oval.

Với video Vw × Vh và vùng hiển thị W × H, scale = max(W/Vw, H/Vh). Vùng cắt trong video có width = W/scale và height = H/scale; tọa độ đầu là ((Vw-width)/2, (Vh-height)/2). Canvas vẽ vùng đó và tạo JPEG chất lượng 0,9. Video xem trước được lật như gương, còn ảnh canvas lấy từ video gốc; ellipse ở giữa đối xứng nên miền chọn không đổi.

## Kiểm tra ảnh ở backend
extract_embedding từ chối ảnh rỗng hoặc lớn hơn 10 MiB. OpenCV giải mã bytes thành ảnh màu; ảnh không giải mã được trả lỗi. Nếu cạnh dài nhất lớn hơn 1600 pixel, ảnh được thu nhỏ theo cùng tỷ lệ hai chiều. Giới hạn 1600 này khác det_size 640 × 640 của detector: một giới hạn đặt ở ứng dụng, một cấu hình đặt ở model phát hiện.

detect_faces gọi bộ phát hiện trên toàn ảnh đã xử lý. Với mỗi mặt, code tạo đối tượng Face chứa bbox, det_score và kps. Sau đó mới lọc bbox theo oval; ứng dụng không chỉ cắt riêng miền oval rồi bỏ qua phần còn lại trước khi phát hiện.

## Công thức miền oval
Gọi W, H là kích thước ảnh đang kiểm tra. Tâm oval là (W/2, H/2), bán kính dọc ry = min(0,39H, 0,4W/0,75), bán kính ngang rx = 0,75ry. Một điểm (x, y) nằm trong oval khi:
```text
((x - W/2) / rx)² + ((y - H/2) / ry)² ≤ 1
```
Với bbox (x1, y1, x2, y2), code lấy tâm mặt cx = (x1+x2)/2, cy = (y1+y2)/2 và kiểm tra bốn điểm: (x1,cy), (x2,cy), (cx,y1), (cx,y2). Cả bốn phải ở trong oval. Đây là phép kiểm tra xấp xỉ theo bốn điểm giữa cạnh, không phải kiểm tra mọi pixel mặt hoặc bốn góc của khung bao.

## Vì sao nhiều người phía sau vẫn được điểm danh
Nếu toàn ảnh có 5 mặt nhưng chỉ 1 bbox đạt kiểm tra oval, code chọn mặt đó và chỉ chạy recognition cho mặt đó. Không có mặt đạt thì trả lỗi vị trí; từ 2 mặt đạt trở lên thì yêu cầu chỉ một người trong oval. Người đứng ngoài oval không tham gia so khớp, nhưng detector vẫn phải phát hiện họ. Oval cũng không phải cơ chế kiểm tra người thật hay chống dùng ảnh chụp.

---
# 5 Embedding căn chỉnh và phép so khớp
## Embedding là gì
Embedding là dãy số biểu diễn đặc trưng khuôn mặt. Có thể hình dung model đặt các ảnh vào một không gian: ảnh của cùng một người thường có hướng vector gần nhau, ảnh của người khác thường khác hơn. Mỗi phần tử không mang ý nghĩa đơn giản như “độ dài mũi” hay “màu mắt”; các đặc trưng được học trong quá trình huấn luyện sẵn của model.

Hàm embed_face gọi models["recognition"].get(image, face). Trong lớp ArcFaceONNX của thư viện đang cài, get sử dụng face.kps để norm_crop, sau đó get_feat tạo vector. Căn chỉnh giúp đưa mặt về tư thế và kích thước đầu vào mà model cần. Mốc mặt do detector trả về; không có nghĩa dự án phải chạy thêm mọi model landmark trong thư mục.

## Chuẩn hóa L2
extract_embedding chuyển kết quả sang float32 rồi chia cho độ dài vector. Với v = (v1, v2, …, vd), độ dài L2 là căn bậc hai của tổng bình phương các phần tử.
```text
norm(v) = sqrt(v1² + v2² + ... + vd²)
u = v / max(norm(v), 10⁻¹²)
```
Số 10⁻¹² tránh phép chia cho 0; nó không phải ngưỡng nhận diện. Chuẩn hóa làm vector có độ dài gần 1 trong trường hợp bình thường, để phép so khớp chủ yếu xét hướng thay vì độ lớn.

## Cosine similarity và np.dot
Cosine similarity giữa hai vector a, b bằng tích vô hướng chia cho tích độ dài. Vì cả vector đăng ký và vector mới đã chuẩn hóa, chương trình dùng np.dot để tính trực tiếp điểm tương đồng.
```text
cosine(a,b) = sum(ai × bi) / (norm(a) × norm(b))
Nếu norm(a) = norm(b) = 1 thì cosine(a,b) = sum(ai × bi)
```
Ví dụ giản lược hai chiều: vector đăng ký (1,0) và vector mới (0,8; 0,6) có độ dài 1, nên điểm bằng 0,8. Vector thực tế có nhiều chiều hơn; ví dụ này chỉ giúp thấy cách tính, không mô phỏng đầy đủ khuôn mặt.

## Ngưỡng 0 phẩy 70 thực sự có nghĩa gì
recognize chọn điểm lớn nhất trong lớp. Điểm dưới 0,70 trả unknown; từ 0,70 trở lên chuyển sang ghi điểm danh. Ví dụ các điểm 0,83; 0,51; 0,28 thì chọn học sinh có 0,83. Nếu cao nhất là 0,64 thì không chọn ai.

0,83 không có nghĩa “83% chắc chắn đúng”, và 0,70 không có nghĩa “độ chính xác 70%”. Đây là ngưỡng trên điểm tương đồng. Tăng ngưỡng thường làm khó chấp nhận hơn; giảm ngưỡng làm dễ chấp nhận hơn. Muốn chọn ngưỡng phù hợp phải đo trên ảnh đại diện. Hiện code cũng chưa kiểm tra chênh lệch giữa ứng viên thứ nhất và thứ hai: 0,81 so với 0,80 vẫn chọn người thứ nhất.

---
# 6 Đăng ký học sinh từ ảnh thành hồ sơ
## Luồng create_student
Frontend gửi POST /api/students bằng multipart form gồm class_id, name, code, images và use_guide. Chế độ webcam hiển thị oval dọc và gửi một ảnh vừa chụp; chế độ tải ảnh cho phép chọn từ 1 đến 5 ảnh. Camera đăng ký áp dụng cùng oval với điểm danh: chỉ một mặt đạt phép kiểm tra oval, người bên ngoài được bỏ qua. Frontend cắt ảnh theo vùng hiển thị và gửi use_guide=true. Với ảnh tải lên, use_guide=false và từng ảnh vẫn phải có đúng một mặt trong toàn ảnh vì không có thao tác chọn oval trên ảnh tải lên.

Backend bỏ khoảng trắng đầu cuối tên và mã, chuyển mã thành chữ hoa. Tên dài tối đa 100 ký tự; mã từ 1 đến 30 ký tự, chỉ dùng chữ A–Z, số, dấu gạch ngang và gạch dưới. Mã học sinh là duy nhất trên toàn database, không chỉ trong một lớp. Schema hiện gắn mỗi học sinh với một class_id.

Trước khi chạy AI, chương trình kiểm tra lớp tồn tại và mã chưa có. Sau đó mỗi ảnh được đưa qua extract_embedding để tạo một vector đã chuẩn hóa. Nếu bất kỳ ảnh nào hỏng hoặc số mặt hợp lệ theo chế độ không đúng một, yêu cầu thất bại và không thêm học sinh dở dang.

## Gộp nhiều ảnh thành một vector
Với ảnh thứ hai trở đi, code so vector với vector ảnh đầu tiên. Nếu có điểm dưới 0,40 thì từ chối vì có thể ảnh không cùng người. Đây là kiểm tra sơ bộ, không đảm bảo tuyệt đối mọi ảnh cùng danh tính và không phải so tất cả các cặp ảnh.
```text
u1, u2, ..., un = vector chuẩn hóa của từng ảnh
Nếu dot(u1, ui) < 0,40 với bất kỳ i > 1: từ chối
m = (u1 + u2 + ... + un) / n
embedding_lưu = m / max(norm(m), 10⁻¹²)
```
Ngưỡng 0,40 kiểm tra bộ ảnh đăng ký; ngưỡng 0,70 quyết định nhận diện khi điểm danh. Chúng có vai trò khác nhau. Vector trung bình giúp gom thông tin của các ảnh thành một đại diện, nhưng không bảo đảm cứ thêm ảnh là tốt hơn: ảnh mờ hoặc khác điều kiện quá nhiều có thể làm đại diện kém phù hợp.

## Chính xác là lưu những gì
students lưu ID, lớp, mã, tên, embedding dạng JSON trong cột TEXT, số ảnh photo_count và ngày created_on. Backend không ghi ảnh gốc thành bộ dataset của ứng dụng. Ảnh vẫn đi qua upload và bộ nhớ hoặc file tạm của framework để xử lý; không lưu lâu dài không có nghĩa ảnh chưa từng được gửi đến máy chủ.

Nếu đăng ký ba ảnh, photo_count bằng 3 nhưng chỉ có một vector đại diện trong hàng học sinh. Không có ba model riêng được train. Khi đổi sang model nhận diện khác, vector cũ có thể không còn tương thích; vì không giữ ảnh gốc, cần kế hoạch đăng ký lại hoặc nguồn ảnh hợp lệ để tạo lại vector.

---
# 7 Nhận diện và ghi điểm danh theo buổi
## Theo dõi một lần bấm chụp
1. recognize nhận class_id, session_id và ảnh. Thiếu session_id trả HTTP 400.
2. require_class xác nhận lớp; require_session xác nhận buổi thuộc lớp, đang mở, đúng ngày và giờ.
3. Truy vấn các học sinh của lớp. Lớp rỗng bị từ chối trước khi trích vector.
4. extract_embedding chạy detector, lọc oval, trích và chuẩn hóa vector của đúng một mặt được chọn.
5. Đọc JSON embedding từng học sinh, tính np.dot với vector mới và chọn cặp có điểm cao nhất.
6. Điểm dưới 0,70 trả unknown. Nếu đạt, gọi record_attendance.
7. record_attendance kiểm tra lại buổi trong giao dịch ghi, thêm bản ghi nếu chưa có rồi trả kết quả.

Tập tìm kiếm chỉ là lớp đang chọn. Người đăng ký ở lớp khác không được đưa vào tập ứng viên của lớp này. Tuy vậy, điều này không bảo đảm người ngoài lớp không bao giờ bị nhận nhầm thành một người trong lớp nếu điểm so khớp vượt ngưỡng.

## Vì sao phải kiểm tra buổi hai lần
Lần đầu tránh tốn AI cho yêu cầu chắc chắn không hợp lệ. Lần thứ hai xử lý trường hợp giáo viên đóng buổi hoặc hết giờ trong lúc AI đang chạy. Khi đó model có thể đã nhận ra nhưng chương trình vẫn không ghi. Đây là bảo vệ dữ liệu trước trạng thái thay đổi, không phải chạy nhận diện lần thứ hai.

## Chống trùng bằng database
session_attendance có UNIQUE(session_id, student_id). record_attendance dùng BEGIN IMMEDIATE để bắt đầu giao dịch ghi và INSERT OR IGNORE. Nếu hàng đã tồn tại thì không tạo hàng thứ hai, trả duplicate và lấy lại giờ của lần đầu. Ràng buộc database bảo vệ cả trường hợp nhiều request gần như đồng thời.

Ví dụ An điểm danh buổi sáng lúc 08:05, chụp lại lúc 08:10: vẫn giữ 08:05. An điểm danh buổi chiều lúc 13:05: có thêm một hàng vì session_id khác. Tổng hợp ngày vẫn tính An là một học sinh có mặt.

| Kết quả | Ý nghĩa | Ghi mới |
| success | Nhận ra và chưa điểm danh buổi này | Có |
| duplicate | Đã có bản ghi trong buổi này | Không |
| unknown | Điểm cao nhất dưới 0,70 | Không |
| HTTP 400 | Thiếu buổi, ảnh lỗi, mặt không hợp lệ hoặc lớp rỗng | Không |
| HTTP 404 | Không tìm thấy lớp, buổi hoặc học sinh tương ứng | Không |
| HTTP 409 | Buổi đóng hoặc ngoài ngày và giờ hợp lệ | Không |

---
# 8 Cơ sở dữ liệu và cách đọc thống kê
## Các bảng và quan hệ
| Bảng hoặc view | Nội dung | Quy tắc đáng chú ý |
| classes | Tên lớp, môn, giáo viên | Tên lớp duy nhất |
| students | Hồ sơ và vector khuôn mặt | Mã duy nhất; mỗi hàng thuộc một lớp |
| sessions | Tên buổi, lớp, ngày, giờ, trạng thái | Tên buổi không trùng trong cùng lớp và ngày |
| session_attendance | Học sinh, buổi, giờ, cách điểm danh, điểm tương đồng | Một hàng cho mỗi cặp học sinh và buổi |
| class_attendance | Dữ liệu điểm danh ngày từ phiên bản cũ | Một hàng cho mỗi học sinh và ngày |
| daily_attendance | View tổng hợp bảng cũ và dữ liệu theo buổi | Một hàng cho mỗi học sinh và ngày |

Quan hệ chính là classes → students, classes → sessions và sessions → session_attendance ← students. View là truy vấn được đặt tên, không phải một bản sao dữ liệu mà ứng dụng phải tự đồng bộ sau mỗi lượt điểm danh.

## Theo buổi khác theo ngày
Khi có session_id, roster nối students với session_attendance của buổi đó. Khi không có session_id, roster nối với daily_attendance của ngày chọn. LEFT JOIN giữ cả người chưa có bản ghi; time là NULL thì giao diện hiển thị Chưa điểm danh.

daily_attendance dùng UNION ALL gộp dữ liệu cũ và mới, rồi GROUP BY student_id, day và MIN(time). Vì vậy một người có mặt ở nhiều buổi vẫn được tính một lần trong ngày, với giờ sớm nhất. Không cộng tất cả lượt điểm danh rồi coi đó là số học sinh.

Ví dụ lớp có 30 học sinh, buổi sáng có 20 người, buổi chiều có 15 người, trong đó 10 người trùng nhau. Tổng hợp ngày có 25 người, không phải 35. Tỷ lệ ngày là 25/30, còn tỷ lệ từng buổi lần lượt là 20/30 và 15/30.

## Dashboard và CSV
dashboard dùng cùng view ngày, tính tỷ lệ làm tròn, xu hướng 7 ngày và tối đa 8 mục gần đây. Giờ của các mục này là giờ đầu tiên trong ngày của mỗi người theo view; không phải nhật ký mọi lần chụp hoặc mọi buổi mới nhất. Dashboard không phải báo cáo tỷ lệ tham dự tất cả tiết học.

CSV có mã, tên, ngày, trạng thái, giờ, phương thức và buổi. Chọn Tổng hợp ngày thì xuất dữ liệu gộp gồm lịch sử cũ; chọn một buổi thì chỉ xuất buổi đó. Code dùng UTF-8 BOM để hỗ trợ tiếng Việt trong Excel và thêm dấu nháy đơn trước tên hoặc tên buổi có tiền tố dễ bị hiểu thành công thức.

created_on chỉ lưu ngày. Học sinh chưa đăng ký ở ngày đang xem bị loại khỏi danh sách, nhưng đây không phải lịch sử đầy đủ sĩ số theo từng thời điểm trong ngày. Chưa điểm danh cũng chưa đồng nghĩa nghỉ không phép; ứng dụng chưa có nghiệp vụ phân loại vắng, muộn hoặc có phép.

---
# 9 Các file và thư mục dùng để làm gì
## Mã nguồn bạn nên đọc
| Đường dẫn tương đối | Vai trò |
| start.ps1 | Kiểm tra môi trường và chạy máy chủ local |
| backend/app.py | Tạo FastAPI, gắn router API, phục vụ trang chủ, static và health |
| backend/classroom.py | Nghiệp vụ lớp học, schema, xử lý ảnh, so khớp, buổi học, dashboard và CSV |
| backend/face_engine.py | Khởi tạo model dùng chung trên CPU |
| backend/requirements.txt | Danh sách thư viện Python; hiện chưa khóa phiên bản |
| backend/test_classroom.py | Kiểm thử nghiệp vụ với database tạm và dữ liệu mô phỏng |
| frontend/index.html | Khung giao diện và các form |
| frontend/styles.css | Màu, cỡ chữ, bố cục, oval và thích ứng màn hình |
| frontend/app.js | State, gọi API, camera, chụp ảnh, danh sách, dashboard và buổi học |
| frontend/assets/huce-logo.png | Logo sử dụng trên giao diện |
| frontend/assets/SOURCE.md | Ghi nguồn tài nguyên logo |
| tests/attendance-guide.test.cjs | Kiểm tra cách cắt vùng camera cho đúng khung nhìn |
| tests/enrollment.test.cjs | Kiểm tra camera đăng ký và một số hành vi buổi học bằng mô phỏng |
| evaluation/evaluate.py | Đánh giá nhận diện chạy riêng, không nằm trong luồng web |
| evaluation/test_evaluate.py | Kiểm thử công cụ đánh giá |
| evaluation/samples.csv | Danh sách ảnh kiểm thử và nhãn thật; hiện mới có tiêu đề |
| evaluation/README.md | Cách chuẩn bị dữ liệu và đọc báo cáo đánh giá |

## Môi trường dữ liệu và tài liệu
| Đường dẫn | Vai trò và lưu ý |
| .python | Python nền đi kèm dự án, được môi trường ảo tham chiếu |
| .venv | Thư viện và Python launcher của môi trường ảo; không phải code bạn tự viết |
| .insightface/models/buffalo_l | Trọng số ONNX đã có sẵn; cần để chạy AI |
| backend/classroom.db | Dữ liệu thực của ứng dụng; cần sao lưu trước khi thay schema |
| backend/backups | Bản sao database trước cập nhật; không được web đọc để điểm danh |
| evaluation/data và reports | Vị trí dữ liệu đánh giá và báo cáo khi sử dụng công cụ |
| docs | Word, bản giải thích Markdown và ảnh minh họa giao diện |
| README.md | Tổng quan, hướng dẫn vận hành và lịch học cố định |
| server.log và server-error.log | Log khi máy chủ được chạy với chuyển hướng đầu ra |
| __pycache__ | Bytecode Python sinh tự động; khác với dữ liệu học sinh |
| .git và .gitignore | Lịch sử mã nguồn và quy tắc bỏ qua file khi quản lý Git |

Nếu thấy thư mục uv-cache ở một môi trường khác, đó thường là cache tải và xây gói của công cụ uv, không phải dữ liệu nhận diện. Trong cấu trúc gốc kiểm tra cho bản tài liệu này không có uv-cache. Không được nhầm cache với .python, .venv, .insightface hoặc classroom.db rồi xóa tất cả.

---
# 10 Đọc code backend theo nhóm hàm
## Khởi tạo và truy cập dữ liệu
database là context manager: mở kết nối SQLite, bật foreign_keys, trả hàng dạng sqlite3.Row, commit nếu thành công, rollback nếu lỗi và luôn đóng kết nối. Các giá trị truy vấn được truyền bằng placeholder ?, giúp tách giá trị người dùng khỏi cú pháp SQL.

init_db tạo bảng, chỉ mục và view nếu chưa có. Hàm chạy khi module classroom được import. Nó không xóa lịch sử cũ. Tuy nhiên CREATE IF NOT EXISTS không tự nâng cấp mọi schema tùy ý về sau; khi đổi cấu trúc đã tồn tại vẫn cần kế hoạch migration riêng.

require_class và require_session dùng chung để kiểm tra dữ liệu tồn tại và quyền liên hệ lớp với buổi. Đây là kiểm tra quan hệ dữ liệu, chưa phải xác thực người dùng hoặc phân quyền giáo viên.

## Các nhóm hàm nghiệp vụ
| Nhóm hàm | Trách nhiệm |
| classes và create_class | Đọc hoặc thêm lớp, kiểm tra trùng tên |
| create_student | Kiểm tra form, trích vector ảnh đăng ký, gộp và lưu hồ sơ |
| face_inside_guide | Kiểm tra bốn điểm của bbox với phương trình ellipse |
| detect_faces và embed_face | Gọi riêng model phát hiện và model nhận diện |
| extract_embedding | Kiểm tra ảnh, resize, chọn mặt, trích và chuẩn hóa vector |
| recognize | Tìm học sinh gần nhất trong lớp và áp dụng ngưỡng |
| record_attendance | Kiểm tra buổi lần cuối và ghi chống trùng |
| list_sessions và create_session | Liệt kê hoặc thêm buổi trong lớp |
| change_session_status | Chuyển trạng thái open hoặc closed |
| roster và get_roster | Ghép học sinh với kết quả theo ngày hoặc buổi |
| dashboard và export | Tổng hợp dữ liệu hoặc tạo file CSV |

## AI_LOCK không phải khóa chống trùng
AI_LOCK là threading.Lock dùng quanh từng lời gọi detector và recognition trong một process. Mục đích là tránh nhiều thread cùng gọi các model dùng chung tại một thời điểm. Khóa được nhả giữa phát hiện và trích vector, nên không bao trọn cả request.

BEGIN IMMEDIATE và UNIQUE trong SQLite mới bảo vệ giao dịch điểm danh và chống tạo trùng hàng. Nếu chạy nhiều process, mỗi process có AI_LOCK riêng; khóa Python này không điều phối tất cả máy hoặc tất cả process. Nhiều request đồng thời vẫn có thể phải chờ model hoặc database.

Không còn luồng nhân viên riêng: register.py, database.py, models.py, collect_dataset.py, generate_embeddings.py, recognize.py và attendance_service.py thuộc phần cũ đã gỡ. Không dùng tên các file đó để giải thích hoạt động của phiên bản hiện tại.

---
# 11 Frontend quản lý camera và dữ liệu thế nào
## Trang đơn dùng JavaScript thuần
index.html có các phần giao diện được bật hoặc ẩn bằng thuộc tính hidden. switchView đổi mục đang xem và tải dữ liệu tương ứng. Dự án không dùng React hoặc Vue và không có các URL riêng như /lop-hoc cho từng tab; điểm vào chính là đường dẫn /.

state giữ classes, students, classId, view, ngày, bộ lọc, stream camera, trạng thái loading và recognizing, danh sách sessions cùng sessionId. Đây là bộ nhớ của trang. Refresh làm state khởi tạo lại, sau đó dữ liệu được lấy lại từ database qua API.

api gọi fetch với tiền tố /api, đọc JSON và chuyển lỗi backend thành thông báo. loadClasses nạp lớp và ngày máy chủ. loadRoster tải buổi, xác định lựa chọn rồi tải danh sách. renderStats tính số có mặt trên toàn danh sách đã tải; ô tìm kiếm chỉ lọc hàng hiển thị, không làm đổi tổng sĩ số.

## Tránh kết quả tải chậm ghi đè lớp đang chọn
rosterRequest tăng mỗi lần tải mới. Khi response về, code chỉ cập nhật nếu số request vẫn mới nhất. Ví dụ vừa chọn lớp A rồi chọn B, response A đến muộn sẽ không ghi đè bảng B. Đây là bỏ qua response cũ, không phải hủy tính toán của request đó trên backend.

Khi nhận diện, recognizing khóa thao tác chụp, chọn lớp và chọn buổi để tránh đổi ngữ cảnh trong lúc chờ. Code giữ classId và sessionId cho request đang chạy. Khi xong, finally khôi phục điều khiển theo trạng thái buổi.

## Camera điểm danh và camera đăng ký
Điểm danh dùng state.stream, ảnh chụp được cắt theo vùng xem và gửi nhận diện. Đăng ký dùng enrollment riêng với mode, stream, photo, url và request. Webcam đăng ký chụp một JPEG để xem trước; tải ảnh là nguồn khác và form chỉ gửi nguồn đang được chọn.

Khi đóng form đăng ký, đổi chế độ hoặc rời trang, code dừng camera và thu hồi object URL xem trước. Bộ đếm request giúp dừng cả stream được trả về muộn sau khi người dùng đã đóng form trong lúc trình duyệt đang hỏi quyền camera.

## Một số giới hạn cần hiểu
can_attend được tải từ server để bật tắt nút, không phải đồng hồ tự kiểm tra liên tục. Khi đã đến giờ hoặc vừa qua ngày mà trang vẫn mở lâu, bấm Làm mới hoặc tải lại trang. Backend luôn kiểm tra ngày giờ lại khi điểm danh nên không chỉ tin nút đang bật.

escapeHTML và textContent giúp tên hoặc mã người dùng không bị chèn thành HTML thực thi. Đây là bảo vệ hiển thị cơ bản; không phải hệ thống xác thực hay một cam kết bảo mật toàn diện.

---
# 12 Các API và cách đối chiếu khi báo cáo
Các đường dẫn dưới đây là giao diện HTTP giữa frontend và backend. Có thể xem schema tương tác do FastAPI tạo tại http://127.0.0.1:8000/docs khi máy chủ đang chạy. Gửi POST hoặc PATCH tại đó có thể thay đổi dữ liệu thật, nên chỉ thực hiện khi có chủ đích.

| Phương thức và đường dẫn | Dữ liệu chính và kết quả |
| GET / | Trả frontend/index.html |
| GET /health | Trả trạng thái healthy; không đo chất lượng nhận diện |
| GET /api/classes | Danh sách lớp, sĩ số và ngày hiện tại |
| POST /api/classes | JSON name, subject, teacher; tạo lớp |
| POST /api/students | Multipart class_id, name, code, images, use_guide; tạo hồ sơ mặt |
| GET /api/classes/{id}/sessions | Query day; trả các buổi và can_attend |
| POST /api/classes/{id}/sessions | JSON name, day, starts_at, ends_at; tạo buổi đóng |
| PATCH /api/classes/{id}/sessions/{sid} | JSON status open hoặc closed |
| POST /api/classes/{id}/recognize | Query session_id, multipart image; nhận diện và ghi |
| GET /api/classes/{id}/roster | Query day, session_id tùy chọn; danh sách và kết quả |
| GET /api/classes/{id}/export | Query như roster; trả CSV tải xuống |
| GET /api/dashboard | Tổng hợp ngày hiện tại và xu hướng 7 ngày |

## Ví dụ dữ liệu tạo buổi
```json
{
  "name": "Buổi sáng",
  "day": "2026-10-28",
  "starts_at": "08:00",
  "ends_at": "10:00"
}
```
Buổi tạo thành công trả ID và vẫn đang đóng. Gọi PATCH với {"status":"open"} để mở. Mở một buổi tương lai không làm buổi đó điểm danh được ngay vì require_session vẫn kiểm tra ngày giờ.

## Những trường hợp không nên hiểu nhầm
Tên trường method hỗ trợ hiển thị nhãn manual cho dữ liệu có phương thức đó, nhưng hiện không có nút hay API điểm danh thủ công cho người dùng. Chỉ nhìn thấy nhãn Thủ công trong code không có nghĩa tính năng đã hoàn chỉnh.

API roster có session_id thì ngày của buổi là ngày thực sự dùng để truy vấn, thay vì tin một query day trái ngược. API cũng kiểm tra buổi thuộc lớp. Frontend chọn ngày tương lai được để quản lý buổi, song điểm danh vẫn chỉ được trong ngày hiện tại của server.

---
# 13 Kiểm thử AI và vấn đề tốc độ
## Các bài test chứng minh điều gì
backend/test_classroom.py kiểm tra trùng lớp và mã, chống trùng buổi, hai buổi cùng ngày, dữ liệu cũ, đóng buổi khi đang nhận diện, ràng buộc giờ và lớp, oval, dashboard và CSV. Database tạm và vector mô phỏng giúp kiểm tra logic một cách lặp lại được.

tests dùng node:test và mô phỏng DOM, camera, fetch để kiểm tra cắt ảnh và thao tác giao diện. Các kiểm thử đó không thay thế việc dùng webcam thật. Kết quả 15 bài backend và 9 bài frontend đạt ở lần kiểm tra sau cập nhật oval đăng ký không phải bằng chứng model có độ chính xác 100%.
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend -p test_classroom.py
node --test tests/attendance-guide.test.cjs tests/enrollment.test.cjs
```

## Công cụ evaluation chạy riêng
evaluate.py đọc database bằng chế độ chỉ đọc, lấy vector đã đăng ký và so với ảnh mới trong samples.csv. Công cụ không ghi điểm danh, không tự thay ngưỡng của web và không train model. Mặc định nó yêu cầu một mặt trong toàn ảnh; tùy chọn --guide áp dụng kiểm tra oval trên ảnh đã cắt đúng vùng camera.

validation dùng để so sánh ngưỡng; test dùng để đánh giá độc lập sau khi chốt ngưỡng. Không nên dùng lại ảnh đăng ký làm ảnh test hoặc chia các frame gần giống từ cùng video sang cả hai tập. samples.csv hiện chỉ có dòng tiêu đề, nên chưa có kết quả đo trên dữ liệu người thật để công bố.

Báo cáo phân biệt nhận đúng người đã đăng ký, nhận sai danh tính, từ chối người quen, chấp nhận nhầm người lạ và lỗi xử lý. Nó cũng ghi thời gian trung bình và p95, nhưng thời gian này không bao gồm camera, upload HTTP, khởi động model hoặc ghi điểm danh. Không so trực tiếp số đó với toàn bộ thời gian người dùng chờ trên web.

## Vì sao có lúc chờ lâu
Tổng thời gian gồm chụp và mã hóa JPEG, upload, giải mã và resize, chờ AI_LOCK, detector, recognition, đọc và so vector, ghi SQLite, rồi tải lại giao diện. Mô hình dùng CPU; lần khởi động phải nạp model. Lớp lớn hơn làm nhiều phép so hơn, còn nhiều người trong ảnh vẫn tạo công việc cho detector dù chỉ một người được trích vector.

So khớp hiện tại duyệt tất cả vector của lớp với độ phức tạp xấp xỉ O(N × d), N là số học sinh và d là chiều vector. Chưa có cache vector hoặc chỉ mục tìm kiếm gần đúng. Tính năng buổi học không thêm lượt suy luận AI, nhưng có thêm kiểm tra và truy vấn dữ liệu; chưa có phép đo để cam kết thời gian tuyệt đối không tăng.

---
# 14 Giới hạn hiện tại và cách xử lý lỗi
## Các chức năng chưa có
Chưa có liveness hoặc chống giả mạo, nên không thể khẳng định người trước camera là người thật chỉ từ việc nhận diện đạt. Chưa có đăng nhập và phân quyền giáo viên, quản lý người dùng, chỉnh sửa hoặc xóa hồ sơ bằng API riêng, lịch sử chuyển lớp, một học sinh tham gia nhiều lớp, quản lý vắng có phép hoặc đi muộn.

Chưa có kiểm tra khuôn mặt đăng ký trùng dưới hai mã, kiểm tra khoảng cách top 1 và top 2, hoặc bộ lọc chất lượng ảnh chi tiết như điểm mờ và độ sáng. Embedding được lưu JSON chưa mã hóa và vẫn là dữ liệu sinh trắc học. Đây là các giới hạn của phiên bản hiện tại, không phải các tính năng đã làm nhưng đang ẩn.

Buổi hết giờ không được ghi nhận thêm, nhưng trường status không tự chuyển sang closed bằng tác vụ nền. Giáo viên có thể bấm đóng. Chưa có API sửa giờ hoặc xóa buổi. Việc mở đóng chỉ là trạng thái cho phép, còn điều kiện ngày giờ vẫn phải đúng.

## Các lỗi thường gặp
| Hiện tượng | Cách hiểu và kiểm tra |
| No Python at một đường dẫn uv cũ | .venv đang tham chiếu Python đã mất. Dùng start.ps1; nếu .python hoặc .venv thiếu thì cần khôi phục môi trường |
| Không mở được trang | Kiểm tra terminal Uvicorn còn chạy và cổng 8000 đúng; xem log lỗi |
| Cổng 8000 đang được dùng | Có tiến trình khác giữ cổng; xác định đúng tiến trình trước khi dừng |
| Camera bị từ chối hoặc đang bận | Cho phép camera cho localhost, kiểm tra thiết bị và ứng dụng đang dùng camera |
| Nút camera không dùng được | Kiểm tra đã có lớp, buổi được chọn, đã mở, đúng giờ; bấm Làm mới |
| Một mặt trong oval vẫn báo lỗi | Bbox có thể sát viền hoặc có mặt thứ hai cũng đạt phép kiểm tra; thử căn giữa và lùi nhẹ |
| unknown | Không có điểm đạt 0,70 trong lớp đang chọn; kiểm tra lớp và ảnh đăng ký, ánh sáng, góc mặt |
| duplicate | Người này đã điểm danh buổi đó; hệ thống giữ giờ lần đầu |
| Thống kê ngày ít hơn tổng các buổi | Đây là số học sinh duy nhất trong ngày, không phải tổng lượt |

Không nên hạ ngưỡng ngay khi có unknown vì có thể tăng nhận nhầm. Trước hết kiểm tra đúng lớp, ảnh đủ rõ và bộ ảnh đăng ký phù hợp. Nếu nhiều trường hợp lặp lại, dùng tập validation để đánh giá thay vì điều chỉnh theo một ảnh đơn lẻ.

---
# 15 Ví dụ xuyên suốt và cách trình bày dự án
## Từ đăng ký đến hai buổi học
Giả sử lớp 10A1 có An mã HS001 và Bình mã HS002. An đăng ký ba ảnh. Backend tạo ba vector chuẩn hóa, kiểm tra các ảnh sau với ảnh đầu ở ngưỡng 0,40, lấy trung bình rồi chuẩn hóa lại. Database lưu một vector đại diện của An và photo_count bằng 3; không có bước train lại model.

Giáo viên tạo buổi sáng 08:00–10:00 và buổi chiều 13:00–15:00, rồi mở buổi sáng. Lúc 08:05, An đứng trong oval, Bình đứng phía sau ngoài oval. Detector tìm cả hai nhưng bộ lọc chỉ chọn An. Recognition tạo vector của An; điểm so với An là 0,83, với Bình là 0,46. Vì 0,83 đạt ngưỡng, backend kiểm tra lại buổi và lưu An lúc 08:05.

Lúc 08:10, An chụp lại. Chương trình vẫn nhận diện ảnh mới nhưng UNIQUE chặn thêm hàng cùng session_id và student_id. Kết quả duplicate trả giờ 08:05. Lúc 10:00, dù giao diện cũ còn cho bấm, backend từ chối do đã hết giờ.

Buổi chiều được mở, An điểm danh lúc 13:05 và tạo bản ghi thứ hai. Khi xem từng buổi, An có một hàng ở mỗi buổi; khi xem tổng hợp ngày hoặc dashboard, An được tính một người với giờ đầu 08:05. Một ảnh người lạ có điểm cao nhất 0,58 trả unknown và không tạo bản ghi.

## Cách mô tả ngắn gọn khi thuyết trình
“Hệ thống của em dùng InsightFace và model ONNX đã huấn luyện sẵn, chạy trên CPU. Khi đăng ký, ảnh khuôn mặt được phát hiện, căn chỉnh, trích embedding và lưu vector đại diện. Khi điểm danh, ứng dụng chỉ chọn một mặt hợp lệ trong oval, tính cosine similarity với học sinh của lớp đang chọn và dùng ngưỡng 0,70 để quyết định. Nếu nhận ra, backend kiểm tra buổi đang mở và đúng giờ rồi ghi SQLite; khóa duy nhất đảm bảo mỗi học sinh chỉ được ghi một lần trong mỗi buổi. Dự án có thí nghiệm tự train SVM trên embedding LFW, không thay đổi InsightFace hoặc luồng web; chưa có liveness.”

## Tự kiểm tra xem đã hiểu chưa
- Nếu thêm một học sinh, thứ thay đổi là bảng students và tập vector so khớp; file trọng số không được train lại.
- Nếu có nhiều mặt ngoài oval, detector vẫn thấy chúng nhưng recognition chỉ xử lý mặt được chọn trong oval.
- Nếu điểm là 0,85, đó là similarity, không phải xác suất đúng 85%.
- Nếu chụp lại cùng buổi, giờ đầu được giữ; khác buổi có thể ghi mới.
- Nếu muốn chứng minh chất lượng AI, cần ảnh kiểm thử độc lập và báo cáo nhận nhầm, bỏ sót, lỗi cùng thời gian; unit test chưa đủ.

## Thứ tự đọc mã để tự tìm hiểu
Đọc start.ps1 → backend/app.py → face_engine.py → schema trong classroom.py → extract_embedding → create_student → recognize → record_attendance → roster và dashboard → frontend/app.js. Sau đó đọc các bài test và evaluation/README.md. Thứ tự này đi từ cách chương trình chạy đến cách AI tạo quyết định và cách giao diện hiển thị quyết định đó.

Các giải thích trong tài liệu phản ánh mã nguồn tại ngày cập nhật. Khi thay model, ngưỡng, schema hoặc nghiệp vụ, cần cập nhật đồng thời phần thuật toán, API và ví dụ để tài liệu tiếp tục khớp với chương trình.

# 16 Thí nghiệm huấn luyện SVM và so sánh cosine
## Mục tiêu và phạm vi
Thí nghiệm huấn luyện bộ phân loại danh tính trên embedding InsightFace, sau đó so sánh với cosine trên cùng dữ liệu. Kết quả được lưu riêng trong trainning/artifacts. Web vẫn dùng cosine và database học sinh hiện có; không nạp SVM để điểm danh.
InsightFace giữ nguyên trọng số pretrained. Phần tự huấn luyện là LinearSVC của scikit-learn. Không gọi đây là tự huấn luyện lại InsightFace hay train bằng dữ liệu học sinh thực tế: các mã HS001 đến HS010 đại diện cho danh tính công khai trong LFW.
## Dữ liệu và cách chia tập
Script download_dataset.py chọn 10 danh tính đã biết, mỗi người 40 ảnh: 20 train, 10 validation và 10 test. Sáu danh tính khác cung cấp ảnh người lạ: ba người cho validation và ba người khác cho test, mỗi người 10 ảnh. Tổng cộng 460 ảnh, không có lớp unknown trong train. Việc chia ảnh dùng seed 42; đây không phải cách chia theo các buổi chụp tại lớp.
extract_embeddings.py dùng buffalo_l, detector 640 × 640 trên CPU. Mỗi ảnh cần đúng một khuôn mặt; InsightFace căn chỉnh theo landmark rồi trích vector 512 chiều. Vector được chuẩn hóa L2, nghĩa là chia cho độ dài vector để đưa về độ dài 1. Nhãn và đường dẫn ảnh được lưu kèm để truy vết.
| Tập | Ảnh ban đầu | Embedding hợp lệ | Bị loại |
| Train | 200 | 167 | 33 |
| Validation | 130 | 115 | 15 |
| Test | 130 | 103 | 27 |
| Tổng | 460 | 385 | 75 |
75 ảnh bị loại vì detector trả nhiều mặt: 60 ảnh có 2 mặt, 12 ảnh có 3 mặt, 3 ảnh có 4 mặt. Chưa kết luận đây đều là nhiều người thật; cần xem ảnh để phân biệt với phát hiện nhầm. Tỷ lệ trích thành công là 385/460, khoảng 83,7%; riêng test là 103/130, khoảng 79,2%.
## SVM học gì
SVM là Support Vector Machine. Có thể hình dung embedding của từng danh tính tạo thành một nhóm điểm; mô hình học ranh giới để phân biệt các nhóm. LinearSVC dùng các hàm điểm tuyến tính trong không gian 512 chiều theo cách một lớp so với các lớp còn lại.
Với vector x, điểm cho danh tính k có dạng s_k = w_k · x + b_k. Các trọng số w_k và độ lệch b_k được học từ embedding và nhãn train. Danh tính có điểm cao nhất là ứng viên; nếu điểm đó thấp hơn ngưỡng thì kết quả là unknown. Điểm này không phải xác suất, có thể âm, và không dùng cùng thang điểm với cosine.
train_classifier.py thử C bằng 0.01, 0.1, 1 và 10. C điều khiển mức phạt sai phân loại so với điều chuẩn. Mô hình dùng class_weight balanced, random_state 42, dual False và tối đa 20000 vòng lặp. Script kiểm tra hội tụ trước khi tiếp tục.
## Chọn cấu hình và ngưỡng
Chỉ 167 embedding train được dùng để fit mô hình. Với mỗi C, script chấm điểm 115 embedding validation rồi thử các ngưỡng tại điểm quan sát được, cùng một ngưỡng từ chối tất cả. Điểm bằng ngưỡng được chấp nhận.
Mục tiêu là tối đa hóa trung bình của hai tỷ lệ: nhận đúng danh tính đã biết và từ chối đúng người lạ. Từ chối nhầm người đã biết được tính là sai. Nếu ngưỡng bằng điểm mục tiêu, ưu tiên ít nhận nhầm người lạ hơn, rồi ngưỡng lớn hơn. Khi chọn giữa các cấu hình C ngang điểm, ưu tiên ít nhận nhầm người lạ hơn rồi C nhỏ hơn.
C được chọn trong lần chạy hiện tại là 0.01. Mô hình và ngưỡng được lưu trước khi đọc test. Không fit lại bằng validation; không dùng kết quả test để chỉnh mô hình trong lần thử nghiệm này. Nếu tiếp tục điều chỉnh dựa trên test, cần tập test mới để đánh giá cuối cùng.
## Đối chứng cosine
Cosine lấy trung bình embedding train của từng danh tính và chuẩn hóa lại để tạo vector tham chiếu. Với vector mới đã chuẩn hóa, tích vô hướng với từng vector tham chiếu chính là cosine similarity. Chọn danh tính có điểm cao nhất và từ chối khi dưới ngưỡng.
Cosine dùng cùng train và validation với SVM; ngưỡng cosine được chọn riêng trên validation theo cùng mục tiêu. Không lấy mẫu tham chiếu từ test. Ngưỡng thử nghiệm này không thay thế ngưỡng 0,70 đang dùng trên web.
## Kết quả trên test
| Chỉ tiêu | SVM | Cosine |
| Nhận đúng danh tính đã biết | 78/78 | 78/78 |
| Từ chối đúng người lạ | 25/25 | 25/25 |
| Nhận nhầm người lạ | 0/25 | 0/25 |
| Tổng dự đoán đúng trên embedding hợp lệ | 103/103 | 103/103 |
Cả hai phương pháp đạt 100% trên 103 embedding test hợp lệ. Thử nghiệm này chưa cho thấy SVM tốt hơn cosine. 27 ảnh test không trích được embedding nằm ngoài mẫu số này; không được tính chúng là từ chối đúng. Nếu tính số ảnh được xử lý và cho kết quả đúng trên toàn bộ 130 ảnh test đầu vào, con số là 103/130.
Ngưỡng đã chọn: SVM -0.373160; cosine 0.653820. Hai giá trị thuộc hai thang điểm khác nhau, không so độ lớn trực tiếp.
## File kết quả và cách chạy lại
Chạy tại thư mục gốc dự án. Nếu đã có embedding, chỉ cần lệnh thứ hai; chạy lại sẽ ghi đè các kết quả tương ứng trong artifacts.
```powershell
.\.venv\Scripts\python.exe -u .\trainning\extract_embeddings.py
.\.venv\Scripts\python.exe -u .\trainning\train_classifier.py
```
svm_classifier.joblib lưu mô hình, C, ngưỡng và phiên bản sklearn. cosine_reference.npz lưu danh tính, vector tham chiếu và ngưỡng cosine. classifier_report.json lưu cấu hình ứng viên, kết quả validation/test, mã SHA256 của dữ liệu đầu vào và thời gian chấm điểm. Hai file svm_test_predictions.csv và cosine_test_predictions.csv ghi dự đoán từng ảnh. rejected_images.csv và extraction_report.json mô tả bước trích embedding.
Đã kiểm tra tải lại mô hình lưu trên đĩa, cơ chế từ chối dưới ngưỡng và không có vector giống hệt giữa các tập. Điều này không loại trừ ảnh gần trùng. Chỉ tải mô hình joblib từ nguồn tin cậy.
## Giới hạn và kết luận dùng trong báo cáo
Tập dữ liệu nhỏ và là LFW công khai, chưa đại diện cho ánh sáng, góc chụp và camera tại lớp. Chưa loại trừ trùng danh tính hoặc ảnh với dữ liệu huấn luyện trước của InsightFace. 25 ảnh người lạ trong test không đủ để khẳng định hệ thống luôn từ chối người lạ.
Thời gian trong classifier_report.json chỉ đo chấm điểm embedding theo lô, không gồm camera, đọc ảnh, phát hiện mặt, trích embedding, HTTP hay ghi database. Không dùng số này để công bố tốc độ điểm danh toàn hệ thống.
Cách trình bày: Em dùng InsightFace pretrained để trích đặc trưng, tự huấn luyện LinearSVC phân loại danh tính và dùng validation chọn cấu hình cùng ngưỡng từ chối. Trên 103 embedding test hợp lệ, SVM và cosine đều đúng 103/103. Em giữ cosine cho web; SVM phục vụ so sánh và báo cáo. Cần thử nghiệm độc lập trên dữ liệu lớp học trước khi kết luận về triển khai thực tế.
