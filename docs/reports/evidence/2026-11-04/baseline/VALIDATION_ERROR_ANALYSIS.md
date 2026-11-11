# Phân tích định lượng lỗi validation

Nội dung do công cụ tổng hợp từ dự đoán thật; chưa có người chấm loại lỗi ngôn ngữ. Một câu có thể xuất hiện ở nhiều model/seed, không được xem các lần lặp là mẫu độc lập.

| Dataset | Model | Nhãn nguồn | Dự đoán | Số quan sát lỗi |
| --- | --- | --- | --- | ---: |
| uts2017-bank | lr | negative | neutral | 3 |
| uts2017-bank | lr | negative | positive | 9 |
| uts2017-bank | lr | neutral | negative | 6 |
| uts2017-bank | lr | neutral | positive | 3 |
| uts2017-bank | lr | positive | negative | 24 |
| uts2017-bank | mbert | negative | positive | 12 |
| uts2017-bank | mbert | neutral | negative | 9 |
| uts2017-bank | mbert | positive | negative | 13 |
| uts2017-bank | phobert | negative | positive | 18 |
| uts2017-bank | phobert | neutral | negative | 9 |
| uts2017-bank | phobert | positive | negative | 4 |
| uts2017-bank | videberta | negative | positive | 46 |
| uts2017-bank | videberta | neutral | negative | 7 |
| uts2017-bank | videberta | neutral | positive | 2 |
| uts2017-bank | videberta | positive | negative | 36 |
| uts2017-bank | visobert | negative | positive | 3 |
| uts2017-bank | visobert | neutral | negative | 9 |
| uts2017-bank | visobert | positive | negative | 2 |
| uts2017-bank | xlmr | negative | positive | 11 |
| uts2017-bank | xlmr | neutral | negative | 9 |
| uts2017-bank | xlmr | positive | negative | 2 |

## Nhận xét dựa trên kết quả

- Đọc confusion theo nhãn nguồn và dự đoán, không suy mọi bất đồng là nhãn nguồn sai.
- uts2017-bank: support validation theo nhãn {'negative': 110.0, 'neutral': 3.0, 'positive': 159.0}; nếu model bỏ sót toàn bộ neutral thì F1 neutral bằng 0. Đọc support cùng accuracy và Macro F1.
- Không so thời gian train để xếp hạng tốc độ khi có tải máy/cold download khác nhau. Các thời gian này được giữ làm bằng chứng chạy, chưa phải benchmark hiệu năng có kiểm soát.
- Chưa đủ cơ sở quy lỗi thành phủ định/mỉa mai/không dấu chỉ từ confusion. Cột human_error_category và human_reviewer trong JSONL để trống, dành cho lượt đọc độc lập.
- So sánh cân bằng lớp/threshold cần được chạy riêng trên validation; không điều chỉnh bằng final test hoặc đưa model ngân hàng vào ứng dụng phim.
