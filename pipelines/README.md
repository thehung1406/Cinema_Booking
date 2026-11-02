# Offline ML pipelines

Training/evaluation lives in `pipelines/ml`, separate from every API image and request.
Run from this directory with a dedicated virtual environment and `ml/requirements.txt`.

- `python -m ml.prepare_samples --help`: create reviewed, grouped splits; draft samples are not approved training data.
- `python -m ml.train_sentiment --help`: train sklearn/PhoBERT offline, keep dataset fingerprints and model metadata.
- `python -m ml.evaluate_sentiment --help`: evaluate frozen held-out data using the standalone predictor.
- `python -m ml.train_chat --help`: train the optional adapter offline with an explicit base model revision.
- `python -m ml.serve_chat --help`: optional separate private inference process; never train during an API request.
- `python -m ml.import_knowledge reviewed.json --origin http://127.0.0.1:8080/api`: explicit owner API import using `AI_IMPORT_TOKEN` with knowledge.manage. It never opens a legacy database.

Datasets with human review, training runs and artifacts stay ignored. Promote only trusted, evaluated model files into the ignored root `model-store/`. The Review inference worker mounts that directory read-only at `/models`; its API image does not contain sklearn/transformers/training code. Normalization matches the worker's NFC/whitespace normalization. The local serving directory is currently empty and the sentiment backend is disabled. M10 does not train or promote a production model; supply an independently reviewed/evaluated artifact before enabling inference.
