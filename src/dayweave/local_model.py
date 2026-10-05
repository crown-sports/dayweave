"""Optional local note-selection model; the planning algorithm never depends on it."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException


def create_model_app(path: Path) -> FastAPI:
    """Load existing trusted weights locally and provide bounded, serialized greedy inference."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(str(path), local_files_only=True, trust_remote_code=False)
    network = (
        AutoModelForCausalLM.from_pretrained(
            str(path), local_files_only=True, trust_remote_code=False, dtype=torch.bfloat16, attn_implementation="sdpa"
        )
        .to("cuda")
        .eval()
    )
    lock = threading.Lock()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"state": "ready", "model": path.name, "device": str(network.device)}

    @app.post("/api/chat")
    def chat(body: dict[str, Any]) -> dict[str, Any]:
        messages = body.get("messages")
        if (
            not isinstance(messages, list)
            or len(messages) > 6
            or not all(
                isinstance(item, dict)
                and item.get("role") in {"system", "user", "assistant"}
                and isinstance(item.get("content"), str)
                for item in messages
            )
        ):
            raise HTTPException(400, "Expected bounded text chat messages")
        if sum(len(item["content"]) for item in messages) > 18000:
            raise HTTPException(413, "Capture prompt is too long")
        with lock, torch.inference_mode():
            prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = tokenizer(prompt, return_tensors="pt").to(network.device)
            count = inputs["input_ids"].shape[1]
            if count > 6000:
                raise HTTPException(413, "Capture prompt exceeds 6,000 tokens")
            output = network.generate(
                **inputs, max_new_tokens=640, do_sample=False, pad_token_id=tokenizer.eos_token_id
            )
            result = tokenizer.decode(output[0, count:], skip_special_tokens=True)
        return {"model": path.name, "message": {"role": "assistant", "content": result}, "done": True}

    return app
