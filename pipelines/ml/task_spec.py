"""Dataset-specific label spaces; absent neutral labels are never invented."""
import json
from pathlib import Path

THREE_LABELS=('negative','neutral','positive')


def label_order(directory):
    path=Path(directory)/'task.json'
    labels=tuple(json.loads(path.read_text(encoding='utf-8'))['labels']) if path.is_file() else THREE_LABELS
    if labels not in (THREE_LABELS,('negative','positive')):
        raise ValueError('Unsupported sentiment label space')
    return labels
