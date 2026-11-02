"""Actual LoRA SFT with prompt tokens masked; stores adapter and tokenizer."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from ml.data import load_splits, fingerprint
from ml.chat_format import messages_for


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True); p.add_argument("--output", required=True)
    p.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    p.add_argument("--revision", required=True); p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    splits = load_splits(args.data)
    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model
    from transformers import AutoTokenizer, AutoModelForCausalLM, Trainer, TrainingArguments, DataCollatorForSeq2Seq, set_seed
    set_seed(args.seed)
    out = Path(args.output); out.mkdir(parents=True, exist_ok=False)
    tokenizer = AutoTokenizer.from_pretrained(args.model, revision=args.revision)
    tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(args.model, revision=args.revision, torch_dtype=torch.float32)
    model = get_peft_model(model, LoraConfig(task_type="CAUSAL_LM", r=8, lora_alpha=16, lora_dropout=.05, target_modules=["q_proj", "v_proj"]))
    def encode(row):
        allowed = {e["id"] for e in row["evidence"]}
        if not set(row["evidence_ids"]) <= allowed:
            raise ValueError("Target includes unsupported evidence")
        messages = messages_for(row["question"], row["evidence"])
        prompt = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
        full = tokenizer.apply_chat_template(messages + [{"role": "assistant", "content": json.dumps({"evidence_ids": row["evidence_ids"]}, ensure_ascii=False)}], tokenize=True)
        if len(full) > 1024 or full[:len(prompt)] != prompt:
            raise ValueError("Example too long or chat template prefix mismatch; review the example")
        return {"input_ids": full, "attention_mask": [1]*len(full), "labels": [-100]*len(prompt)+full[len(prompt):]}
    trainer = Trainer(model=model, args=TrainingArguments(output_dir=str(out / "checkpoints"), seed=args.seed,
        num_train_epochs=args.epochs, learning_rate=2e-4, per_device_train_batch_size=1, gradient_accumulation_steps=8,
        per_device_eval_batch_size=1, eval_strategy="epoch", save_strategy="epoch", load_best_model_at_end=True,
        save_total_limit=1, report_to=[]), train_dataset=Dataset.from_list([encode(r) for r in splits["train"]]),
        eval_dataset=Dataset.from_list([encode(r) for r in splits["validation"]]),
        data_collator=DataCollatorForSeq2Seq(tokenizer, padding=True, label_pad_token_id=-100))
    trainer.train(); model.save_pretrained(out); tokenizer.save_pretrained(out)
    (out / "metadata.json").write_text(json.dumps(dict(vars(args), data_sha256=fingerprint(args.data), model_version=out.name,
        validation=trainer.evaluate(), task="grounded evidence selection; exact source rendering"), indent=2), encoding="utf-8")
    (out / "environment.txt").write_text(subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True), encoding="utf-8")


if __name__ == "__main__":
    main()
