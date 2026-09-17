"""Private model process: python -m ml.serve_chat --model ... --revision ... [--adapter ...]."""
import argparse
import json
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from ml.chat_format import messages_for


class SelectionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    evidence: list[dict] = Field(max_length=20)


def load_model(model_id, revision, adapter=None):
    from transformers import AutoModelForCausalLM, AutoTokenizer
    model = AutoModelForCausalLM.from_pretrained(model_id, revision=revision)
    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
    if adapter:
        metadata = json.loads(Path(adapter, "metadata.json").read_text(encoding="utf-8"))
        if metadata["model"] != model_id or metadata["revision"] != revision:
            raise ValueError("Adapter/base model revision mismatch")
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, adapter)
    model.eval()
    return model, tokenizer


def generate(model, tokenizer, question, evidence):
    import torch
    prompt = tokenizer.apply_chat_template(messages_for(question, evidence), tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt")
    if inputs.input_ids.shape[-1] > 4096:
        raise ValueError("Context too long")
    with torch.inference_mode():
        output = model.generate(**inputs, max_new_tokens=128, do_sample=False, pad_token_id=tokenizer.eos_token_id)
    text = tokenizer.decode(output[0][inputs.input_ids.shape[-1]:], skip_special_tokens=True).strip()
    payload = json.loads(text)
    ids = payload.get("evidence_ids")
    allowed = {e["id"] for e in evidence}
    if not isinstance(ids, list) or any(not isinstance(i, str) or i not in allowed for i in ids):
        raise ValueError("Invalid evidence selection")
    return {"evidence_ids": list(dict.fromkeys(ids))}


def create_app(model_id, revision, adapter=None):
    slot = threading.BoundedSemaphore(1)
    @asynccontextmanager
    async def lifespan(app):
        app.state.model, app.state.tokenizer = load_model(model_id, revision, adapter)
        yield
    app = FastAPI(lifespan=lifespan)
    @app.post("/select")
    def select(request: SelectionRequest):
        if not slot.acquire(blocking=False):
            raise HTTPException(503, "Model busy")
        try:
            return generate(app.state.model, app.state.tokenizer, request.question, request.evidence)
        except Exception:
            raise HTTPException(503, "Model could not provide a grounded selection")
        finally:
            slot.release()
    return app


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct"); p.add_argument("--revision", required=True)
    p.add_argument("--adapter"); p.add_argument("--port", type=int, default=8010)
    args = p.parse_args()
    import uvicorn
    uvicorn.run(create_app(args.model, args.revision, args.adapter), host="127.0.0.1", port=args.port)
