# Bảng cấu hình mô hình dự kiến

Các kiến trúc dưới đây lấy từ checkpoint đã pin. Tham số được đếm trên cấu hình classifier 3 lớp, không phải bằng chứng đã train.

| Mô hình | Đặc trưng | Kiến trúc | Layer encoder | Tham số | LR | Epoch dự kiến | Batch × tích lũy | Optimizer |
| --- | --- | --- | ---: | ---: | --- | --- | --- | --- |
| phobert | token IDs + attention mask | RobertaForSequenceClassification | 12 | 135000579 | 2e-05 | 3 | 1 × 8 | adamw_torch |
| visobert | token IDs + attention mask | XLMRobertaForSequenceClassification | 12 | 97568259 | 2e-05 | 3 | 1 × 8 | adamw_torch |
| videberta | token IDs + attention mask | DebertaV2ForSequenceClassification | 12 | 70792707 | 2e-05 | 3 | 1 × 8 | adamw_torch |
| mbert | token IDs + attention mask | BertForSequenceClassification | 12 | 177855747 | 2e-05 | 3 | 1 × 8 | adamw_torch |
| xlmr | token IDs + attention mask | XLMRobertaForSequenceClassification | 12 | 278045955 | 2e-05 | 3 | 1 × 8 | adamw_torch |
| lr | TF-IDF char 2–5 grams | TF-IDF + multinomial LogisticRegression | N/A | N/A | N/A | N/A | N/A | lbfgs; C selected on validation |

Có 18 lượt validation hoàn tất trong thư mục đầu vào. Kết quả, cấu hình thực chạy và hash ở research-evidence.json.
