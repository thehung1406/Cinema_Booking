# Offline ML pipelines

Training, evaluation and dataset preparation live in `pipelines/ml`, separate from every API image and request. Use a dedicated environment and `pipelines/requirements-research.txt`; setup and executable examples are in [AI_RUNBOOK.md](../docs/AI_RUNBOOK.md).

For a new machine, start with [AI_PORTABLE_SETUP.md](../docs/AI_PORTABLE_SETUP.md). `bootstrap_research.py` creates a separate CPU/CUDA environment; source downloads use pinned revisions/checksums. `ml.blind_annotation` prepares independent passes and pre-adjudication agreement. Git-visible measured evidence is under `docs/reports/evidence/2026-11-04`, while raw data and weights stay ignored.

Run modules from the repository root with `pipelines` and the root on `PYTHONPATH`:

- `ml.prepare_samples`: create unreviewed synthetic drafts in a new output directory; these are not reviewed datasets or benchmark evidence.
- `ml.suggest_annotations`, `ml.annotation_app`, `ml.annotations`: AI suggestions, human confirmation and CSV round trips; preserve source/license/synthetic flags.
- `ml.data`, `ml.dataset_audit`: prepare grouped splits, check admission and produce data cards/EDA.
- `ml.tokenization_audit`: measure lengths and truncation after each pinned tokenizer and its actual preprocessing; distribution only, without final model testing.
- `ml.benchmark`: plan/train/evaluate/summarize the model × dataset × seed matrix using pinned config.
- `ml.train_sentiment`, `ml.evaluate_sentiment`, `ml.research_figures`: offline model training, explicit final-test evaluation and figures from completed runs.
- `ml.export_evidence`: export pinned model architecture/parameter tables and actual completed-run metadata separately; missing runs retain their state without zero scores.
- `ml.serve_retrieval`: standalone private embedding/reranking inference, without database access.
- `ml.train_chat`, `ml.serve_chat`: optional offline evidence-selection adapter workflow. The current live chatbot uses Qwen3:4b through Ollama, not a trained adapter.

Knowledge preparation, draft import and isolated replay use `scripts/ai/prepare_knowledge.py`, `scripts/ai/import_knowledge.py`, `scripts/ai/evaluate_rag.py` and `scripts/ai/smoke_rag_answer.py`. The API importer needs `CINEMA_ADMIN_TOKEN` with `knowledge.manage` and never approves documents automatically.

Reviewed datasets, downloaded PDF/model files, training runs and artifacts stay ignored. Promote only trusted, independently evaluated sentiment artifacts into the ignored root `model-store/`; the Review worker mounts them read-only. Its API image does not contain training code. Current sentiment runtime is disabled; the UTS2017_Bank baseline does not establish quality on film reviews.

See [implementation status](../docs/AI_IMPLEMENTATION_STATUS.md), [advisor checklist](../docs/AI_GVHD_CHECKLIST.md) and [public data sources](../docs/AI_DATA_SOURCES.md) for measured results and missing datasets/experiments. Research v3 uses `configs/ai_research.advisor-v3.json`; the original lock stays unchanged. `configs/segmentation.lock.json` pins the external word segmenter/JRE files. No pretrained or newly trained research artifact is promoted automatically to an application worker.
