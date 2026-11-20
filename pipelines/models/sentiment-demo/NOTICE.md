# Nguồn mô hình và thông tin sử dụng

Mô hình ViSoBERT trong gói được dự án Cinema Booking fine-tune từ [uitnlp/visobert](https://huggingface.co/uitnlp/visobert), revision [196a62afad9cbe4f52a54aabad828b13f0eec59a](https://huggingface.co/uitnlp/visobert/blob/196a62afad9cbe4f52a54aabad828b13f0eec59a/README.md). Tác giả mô hình gốc: Nam Nguyen, Thang Phan, Duc-Vu Nguyen và Kiet Nguyen, The UIT Natural Language Processing Group.

Model card tại revision này mô tả mô hình dành cho nghiên cứu và yêu cầu trích dẫn công trình. Giữ thông tin nguồn này khi chia sẻ artifact. Gói dùng cho nghiên cứu/đồ án; không tự gán giấy phép phần mềm của dự án cho trọng số của tác giả gốc.

Công trình cần ghi nhận: Nguyen et al. (2023), *ViSoBERT: A Pre-Trained Language Model for Vietnamese Social Media Text Processing*, EMNLP 2023, trang 5191–5207. [Bài báo chính thức](https://aclanthology.org/2023.emnlp-main.315/).

Thay đổi của dự án: fine-tune và lưu classification head cho `negative`, `neutral`, `positive`; tokenizer giữ cùng nguồn. Bản LR do dự án huấn luyện với đặc trưng TF-IDF trên cùng lượt dữ liệu silver. Cấu hình, phiên bản, nguồn nhãn và checksum dữ liệu được ghi trong metadata, không kèm các bình luận gốc hay nhãn cá nhân. Hai artifact chưa được công bố làm mô hình production.
