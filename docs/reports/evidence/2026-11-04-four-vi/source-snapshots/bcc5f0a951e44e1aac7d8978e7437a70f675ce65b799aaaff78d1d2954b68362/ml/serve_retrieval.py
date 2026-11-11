"""Private CPU/GPU inference service; API owners need no torch or training code."""
import argparse
from collections import OrderedDict
import re
import threading


def create_app(model_id, revision, reranker=None, reranker_revision=None, device=None, fp16=False):
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel, Field
    import numpy as np
    from sentence_transformers import SentenceTransformer, CrossEncoder
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("Embedding model revision must be pinned")
    if reranker and not re.fullmatch(r"[a-f0-9]{40}", reranker_revision or ""):
        raise ValueError("Reranker revision must be pinned")
    model = SentenceTransformer(model_id, revision=revision, trust_remote_code=False, device=device)
    cross = CrossEncoder(reranker, revision=reranker_revision, trust_remote_code=False,
                         device=device, max_length=512) if reranker else None
    if fp16 and cross is not None:
        if str(cross.device).startswith("cpu"):
            raise ValueError("Reranker fp16 requires a GPU")
        cross.model.half()
    slot = threading.BoundedSemaphore(1)
    app = FastAPI(docs_url=None, redoc_url=None)

    class Request(BaseModel):
        query: str = Field(min_length=1, max_length=2000)
        texts: list[str] = Field(min_length=1, max_length=1000)

    cache = OrderedDict()

    def encode_many(texts, kind):
        prefix = f"{kind}: " if "e5" in model_id.lower() else ""
        keys = [prefix + text for text in texts]
        missing = list(dict.fromkeys(key for key in keys if key not in cache))
        if missing:
            vectors = model.encode(missing, normalize_embeddings=True, batch_size=16)
            for key, vector in zip(missing, vectors):
                cache[key] = vector
        result = [cache[key] for key in keys]
        for key in keys:
            cache.move_to_end(key)
        while len(cache) > 4096:
            cache.popitem(last=False)
        return result

    def validate(body):
        if sum(map(len, body.texts)) > 2000000 or any(len(text) > 10000 for text in body.texts):
            raise HTTPException(422, "Inference request too large")
        if not slot.acquire(blocking=False):
            raise HTTPException(503, "Inference busy")

    @app.post("/similarity")
    def similarity(body: Request):
        validate(body)
        try:
            query = encode_many([body.query], "query")[0]
            scores = [float(np.dot(query, vector)) for vector in encode_many(body.texts, "passage")]
            return dict(scores=scores, model=model_id, revision=revision)
        finally:
            slot.release()

    @app.post("/rerank")
    def rerank(body: Request):
        if cross is None:
            raise HTTPException(503, "Reranker not configured")
        validate(body)
        try:
            return dict(scores=[float(value) for value in cross.predict([(body.query, text) for text in body.texts], batch_size=4)],
                        model=reranker, revision=reranker_revision)
        finally:
            slot.release()

    @app.get("/health/ready")
    def ready():
        return dict(status="ready", embedding_model=model_id, revision=revision, reranker=reranker,
                    reranker_revision=reranker_revision, device=str(model.device), reranker_fp16=fp16,
                    reranker_batch_size=4, reranker_max_length=512)
    return app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="intfloat/multilingual-e5-small")
    parser.add_argument("--revision", required=True)
    parser.add_argument("--reranker")
    parser.add_argument("--reranker-revision")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8011)
    parser.add_argument("--device", choices=["cpu", "cuda"])
    parser.add_argument("--fp16", action="store_true", help="Use fp16 for the GPU reranker only")
    args = parser.parse_args()
    import uvicorn
    uvicorn.run(create_app(args.model, args.revision, args.reranker, args.reranker_revision, args.device, args.fp16), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
