# Thử nghiệm bộ phân loại khuôn mặt

Thư mục này chạy độc lập với web, không cập nhật database hay mô hình điểm danh.

## Chạy từ thư mục gốc dự án

```powershell
.\.venv\Scripts\python.exe -u .\trainning\extract_embeddings.py
.\.venv\Scripts\python.exe -u .\trainning\train_classifier.py
```

Nếu đã trích embedding, chỉ cần lệnh thứ hai. Chạy lại sẽ ghi đè các kết quả thử nghiệm tương ứng trong `artifacts/`.

## Bạn tự train phần nào?

InsightFace buffalo_l có sẵn biến ảnh thành vector 512 chiều. Trọng số InsightFace không thay đổi. LinearSVC học các trọng số phân biệt 10 danh tính từ embedding có nhãn trong train. Đây là phần bộ phân loại được huấn luyện trên dữ liệu của bạn.

Script thử C = 0.01, 0.1, 1, 10. C điều khiển mức phạt lỗi khi huấn luyện SVM. Với mỗi cấu hình, script dùng validation để chọn ngưỡng trên điểm SVM cao nhất: dưới ngưỡng thì trả về unknown. Điểm SVM là điểm quyết định, không phải xác suất và có thể âm.

Mục tiêu chọn cấu hình/ngưỡng là trung bình của tỷ lệ nhận đúng danh tính đã biết (tính cả việc từ chối nhầm là sai) và tỷ lệ từ chối đúng người lạ. Nếu bằng điểm, ưu tiên ít nhận nhầm người lạ, rồi C nhỏ hơn. Không huấn luyện lớp unknown và không dùng test để chọn cấu hình. Mô hình và ngưỡng được lưu trước khi đọc test.

Đối chứng cosine lấy vector trung bình của từng danh tính từ train rồi chuẩn hóa. So sánh vector mới với các vector này, chọn điểm cao nhất và dùng ngưỡng chọn riêng trên validation. Không dùng ngưỡng SVM cho cosine.

## Kết quả lần chạy đầu

- Train: 167 embedding, 10 danh tính; validation: 115; test: 103.
- C được chọn: 0.01. SVM và cosine đều đúng 78/78 ảnh người đã biết, từ chối đúng 25/25 ảnh người lạ trên test.
- `svm_classifier.joblib`: mô hình SVM, ngưỡng, cấu hình và phiên bản sklearn.
- `cosine_reference.npz`: vector tham chiếu, danh tính và ngưỡng cosine.
- `classifier_report.json`: cấu hình ứng viên, kết quả validation/test, mã SHA256 của đầu vào và thời gian chấm điểm embedding.
- `svm_test_predictions.csv`, `cosine_test_predictions.csv`: dự đoán từng ảnh để kiểm tra lỗi.

Đã kiểm tra tải lại mô hình lưu trên đĩa, cơ chế từ chối và không có vector giống hệt nhau giữa các tập. Kiểm tra này không loại trừ ảnh gần trùng nhau.

## Giới hạn cần trình bày

100% chỉ áp dụng cho 103 ảnh test đã trích được embedding, không chứng minh độ chính xác 100% ngoài lớp học. Trong 460 ảnh gốc, 75 ảnh bị loại do detector phát hiện nhiều khuôn mặt; test trích thành công 103/130 ảnh. Cần báo cáo tỷ lệ này riêng, không bỏ qua các ảnh lỗi.

LFW là dữ liệu công khai, các mã HS là nhãn thử nghiệm, không phải học sinh thực tế. Chưa loại trừ khả năng trùng danh tính/dữ liệu với dữ liệu huấn luyện trước của InsightFace. Thử nghiệm nhỏ này chưa chứng minh SVM tốt hơn cosine; nên đánh giá thêm dữ liệu lớp học được đồng ý thu thập và chia theo buổi chụp.

Thời gian trong báo cáo chỉ đo chấm điểm embedding theo lô; không bao gồm camera, phát hiện mặt, trích embedding hay mạng. Không suy ra thời gian điểm danh của web từ số này.

Báo cáo đầy đủ đã được gộp vào phần 16 của [tài liệu dự án](../docs/GIAI-THICH-CODE-VA-THUAT-TOAN.md) và [bản Word](../docs/TAI-LIEU-DU-AN-DIEM-DANH.docx). File này giữ hướng dẫn chạy nhanh tại thư mục thí nghiệm.
