# Kiểm thử AI riêng cho hệ thống điểm danh

Công cụ này chạy thủ công, không được web import, không thêm bước nào vào luồng điểm danh. Chỉ đọc classroom.db bằng SQLite mode=ro; không ghi lịch sử và không tự thay ngưỡng 0,70. Không có huấn luyện trong bước này.

## 1. Chuẩn bị ảnh

Chỉ dùng ảnh của người đồng ý tham gia kiểm thử. Giữ dữ liệu trên máy. Bắt đầu với một lớp nhỏ:

- Mỗi học sinh đã đăng ký: chụp các ảnh mới ở nhiều lần chụp, không dùng lại ảnh đăng ký.
- Thêm người chưa đăng ký trong lớp để kiểm tra nhận nhầm người lạ.
- Chụp trong các điều kiện: đủ sáng, thiếu sáng, nghiêng nhẹ, có kính, khoảng cách khác nhau.
- Tách ảnh theo lần/buổi chụp: validation dùng chọn ngưỡng; test để đánh giá cuối cùng. Tránh lấy các khung hình gần giống từ cùng một video rồi chia sang cả hai tập.
- Một người đã đăng ký có thể xuất hiện ở cả validation và test, nhưng phải dùng ảnh độc lập. Với người lạ, ưu tiên những người khác nhau giữa hai tập.

Thư mục:

```text
evaluation/
  evaluate.py       Công cụ chạy riêng
  samples.csv       Danh sách ảnh và nhãn thật, hiện chỉ có tiêu đề
  data/
    validation/    Ảnh để so sánh ngưỡng
    test/          Ảnh đánh giá độc lập sau khi chốt ngưỡng
  reports/         Mỗi lần chạy tạo một thư mục kết quả mới
```

Trong samples.csv, mỗi dòng ứng với một ảnh. Ví dụ minh họa (thay mã bằng mã thật trong lớp):

```csv
path,expected_code,split,condition
data/validation/hs001_sang.jpg,HS001,validation,du_sang
data/validation/nguoi_la01.jpg,,validation,du_sang
data/test/hs001_nghieng.jpg,HS001,test,nghieng
data/test/nguoi_la02.jpg,,test,thieu_sang
```

`expected_code` để trống nghĩa là người không thuộc danh sách đăng ký của lớp đang đánh giá. Mã ghi đúng như database. Không dùng nhãn UNKNOWN làm mã. `path` tương đối từ thư mục chứa samples.csv. File ảnh phải nằm trong thư mục đó hoặc thư mục con, tối đa 10 MiB.

Công cụ chặn ảnh giống hệt bytes trong manifest, kể cả khác tên file. Nó không phát hiện ảnh gần giống hoặc ảnh đã dùng đăng ký: ứng dụng không giữ ảnh đăng ký nên bạn phải tự đảm bảo điều này.

## 2. Chạy từ thư mục dự án

Liệt kê ID lớp:

```powershell
.\.venv\Scripts\python.exe .\evaluation\evaluate.py --list-classes
```

Kiểm tra file và nhãn, chưa chạy AI (thay 2 bằng ID lớp cần đánh giá):

```powershell
.\.venv\Scripts\python.exe .\evaluation\evaluate.py --class-id 2 --check
```

Đánh giá validation ở ngưỡng hiện tại 0,70 và thử thêm 0,40 đến 0,90, bước 0,05:

```powershell
.\.venv\Scripts\python.exe .\evaluation\evaluate.py --class-id 2 --split validation
```

Sau khi chọn ngưỡng bằng validation, chạy test ở đúng ngưỡng đã chọn, ví dụ 0,75:

```powershell
.\.venv\Scripts\python.exe .\evaluation\evaluate.py --class-id 2 --split test --threshold 0.75
```

Test chỉ báo cáo ngưỡng được chỉ định, không quét nhiều ngưỡng. Không liên tục thay ngưỡng theo kết quả test. Công cụ không tự đề xuất một ngưỡng tối ưu khi thiếu dữ liệu hoặc chưa xác định mức chấp nhận nhận nhầm.

Mặc định ảnh cần đúng một mặt trong toàn ảnh: chế độ này đo phần nhận diện độc lập với oval. Nếu muốn đánh giá cả vị trí oval, dùng `--guide` và ảnh phải đã được cắt đúng vùng camera hiển thị như app.js gửi lên. Không dùng ảnh chụp màn hình có cả menu hoặc thanh trình duyệt.

Chạy đánh giá lúc không có người điểm danh. Dù không gọi API hoặc khóa AI của server, một process AI khác vẫn dùng CPU/RAM chung và có thể làm chậm server nếu chạy đồng thời.

## 3. Đọc kết quả

Mỗi lần chạy tạo thư mục riêng trong reports, gồm:

- `summary.json`: cấu hình, ngưỡng, thống kê theo điều kiện, thời gian trung bình và p95.
- `predictions.csv`: nhãn thật, ứng viên gần nhất, điểm số, lỗi xử lý, thời gian từng ảnh.
- `thresholds.csv`: số lượng và tỷ lệ theo từng ngưỡng; mở được trong Excel.

Ứng viên gần nhất trong predictions.csv chưa chắc là kết quả được chấp nhận: phải so score với threshold. Khi điểm bằng nhau, chọn ID lớn hơn, giống code điểm danh hiện tại.

| Trường | Ý nghĩa |
|---|---|
| known | Tổng ảnh của người đã đăng ký |
| unknown | Tổng ảnh người ngoài danh sách |
| errors | Ảnh không xử lý được, không có mặt hoặc số mặt không phù hợp |
| known_correct | Nhận đúng danh tính và đạt ngưỡng |
| known_wrong_identity | Nhận thành học sinh khác và đạt ngưỡng |
| known_rejected | Có vector nhưng điểm dưới ngưỡng dù là người đã đăng ký |
| unknown_accepted | Nhận nhầm người lạ thành một học sinh trong lớp |
| unknown_rejected | Có vector và người lạ được từ chối vì dưới ngưỡng |
| known_correct_rate | known_correct / tất cả ảnh known |
| unknown_accept_rate | unknown_accepted / tất cả ảnh unknown |

Lỗi được báo riêng, không được tính là từ chối đúng người lạ. Tỷ lệ dùng tổng số ảnh của nhóm làm mẫu số, bao gồm ảnh lỗi; phải đọc kèm errors. Nhóm không có ảnh có tỷ lệ null, không phải 0%. Không báo cáo một tỷ lệ accuracy chung rồi bỏ qua lỗi hay người lạ.

Thời gian `processing_ms` đo đọc ảnh, trích xuất đặc trưng và so khớp trong process đánh giá; không bao gồm khởi động model, camera, upload HTTP, đọc gallery ban đầu hoặc ghi điểm danh. Có tính lần suy luận đầu tiên và ảnh lỗi. Đây không phải thời gian người dùng chờ trên web. So sánh hai lần chạy cần cùng máy, cùng dữ liệu, cùng cấu hình và không có tải nền khác.

`gallery_sha256` giúp nhận ra danh sách/vector đăng ký đã thay đổi giữa các lần đo. Công cụ không xuất vector vào báo cáo.

## 4. Bước đã hoàn thành và bước cần dữ liệu thật

Đã có công cụ kiểm tra dữ liệu, chạy nhận diện offline, quét ngưỡng validation và đánh giá test. Chưa có kết quả chính xác trên người thật vì samples.csv chưa được điền ảnh kiểm thử. Không dùng test mô phỏng để công bố độ chính xác AI.

Chạy kiểm tra công cụ (không nạp AI, không dùng database thật):

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s evaluation -p "test_*.py" -v
```
