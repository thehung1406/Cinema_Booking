import pytest
from ml.data import grouped_split, load_splits, write_jsonl


def row(i, text, group=None):
    return dict(id=str(i), text=text, label="positive", group_id=group or str(i), review_status="approved", reviewer="test-fixture",
                source="unit-test", license="test-only")


def test_split_keeps_duplicates_and_groups_together():
    texts = ["Diễn viên thể hiện tâm lý nhân vật rất sâu sắc", "Âm nhạc gợi nhiều cảm xúc", "Kịch bản có kết cấu chặt chẽ",
             "Tôi thích những cảnh hành động", "Màu sắc khung hình rực rỡ", "Một câu chuyện gia đình ấm áp",
             "Phần kết tạo bất ngờ", "Hiệu ứng hình ảnh sống động", "Lời thoại rất gần gũi", "Nhịp kể chuyện hợp lý"]
    rows = [row(i, t) for i, t in enumerate(texts)]
    rows += [row(20, texts[0] + "."), row(21, "Nhân vật xứng đáng được yêu mến", group="0")]
    parts = grouped_split(rows)
    locations = {r["id"]: name for name, samples in parts.items() for r in samples}
    assert locations["0"] == locations["20"] == locations["21"]
    assert all(parts.values())


def test_load_rejects_cross_split_near_duplicates(tmp_path):
    write_jsonl(tmp_path / "train.jsonl", [row(1, "Phim hay và đáng xem")])
    write_jsonl(tmp_path / "validation.jsonl", [row(2, "Phim hay và đáng xem!")])
    write_jsonl(tmp_path / "test.jsonl", [row(3, "Diễn xuất rất ổn")])
    with pytest.raises(ValueError, match="Near-duplicate"):
        load_splits(tmp_path)
