
import os
import sys
import torch
import gc
import logging
import asyncio
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer, BitsAndBytesConfig
from peft import PeftModel
from threading import Thread
import uvicorn
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ModelServer")

app = FastAPI()

# ============================================================
# P0-FIX: Inference concurrency protection - Use AsyncIO Lock to avoid request conflicts
# ============================================================
inference_lock = asyncio.Lock()
pending_requests = 0  # Pending request count

# Global state
model_state = {
    "model": None,
    "tokenizer": None,
    "model_path": None,
    "adapter_path": None,
    "quantization": None
}

@app.get("/queue")
async def get_queue_status():
    """Return inference queue status for frontend display"""
    return {
        "is_busy": inference_lock.locked(),
        "pending_requests": pending_requests
    }

class LoadRequest(BaseModel):
    model_path: str
    adapter_path: Optional[str] = None
    quantization: Optional[str] = None  # '4bit', '8bit', or None

class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]
    max_tokens: int = 512
    temperature: float = 0.7

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "loaded": model_state["model_path"] is not None,
        "model_path": model_state["model_path"],
        "adapter_path": model_state["adapter_path"],
        "quantization": model_state["quantization"]
    }

@app.post("/load")
async def load_model(request: LoadRequest):
    global model_state
    
    target_model = request.model_path
    target_adapter = request.adapter_path
    target_quantization = request.quantization
    
    # Check if reload is needed
    if (model_state["model"] is not None and 
        model_state["model_path"] == target_model and 
        model_state["adapter_path"] == target_adapter and
        model_state["quantization"] == target_quantization):
        logger.info("Model already loaded")
        return {"status": "already_loaded"}

    logger.info(f"Loading model: {target_model}, Adapter: {target_adapter}, Quantization: {target_quantization}")

    try:
        # Release old model
        if model_state["model"] is not None:
            del model_state["model"]
            del model_state["tokenizer"]
            gc.collect()
            torch.cuda.empty_cache()
            model_state["model"] = None
            model_state["tokenizer"] = None

        # Load Tokenizer
        tokenizer = AutoTokenizer.from_pretrained(target_model, trust_remote_code=True)
        
        # Prepare quantization config
        quantization_config = None
        if target_quantization == "4bit":
            logger.info("Using 4-bit quantization")
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
            )
        elif target_quantization == "8bit":
            logger.info("Using 8-bit quantization")
            quantization_config = BitsAndBytesConfig(load_in_8bit=True)
        
        # Load Base Model
        # Always use device_map="auto" to avoid bitsandbytes .to() errors
        # and ensure proper VRAM management
        model_kwargs = {
            "trust_remote_code": True,
            "torch_dtype": torch.float16,
            "device_map": "auto",  # Always set, critical for quantized models
            "low_cpu_mem_usage": True,  # Reduce CPU memory peak
        }
        
        if quantization_config:
            model_kwargs["quantization_config"] = quantization_config
        
        model = AutoModelForCausalLM.from_pretrained(target_model, **model_kwargs)

        # Load Adapter (if exists)
        if target_adapter and target_adapter.lower() != 'none':
             logger.info(f"Loading LoRA adapter from {target_adapter}")
             model = PeftModel.from_pretrained(model, target_adapter)

        model_state["model"] = model
        model_state["tokenizer"] = tokenizer
        model_state["model_path"] = target_model
        model_state["adapter_path"] = target_adapter
        model_state["quantization"] = target_quantization
        
        logger.info("Model loaded successfully")
        return {"status": "loaded"}
        
    except Exception as e:
        logger.error(f"Error loading model: {str(e)}")
        # Clean up on failure
        model_state["model"] = None
        model_state["tokenizer"] = None
        gc.collect()
        torch.cuda.empty_cache()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/unload")
async def unload_model():
    global model_state
    if model_state["model"] is not None:
        logger.info("Unloading model...")
        del model_state["model"]
        del model_state["tokenizer"]
        model_state["model"] = None
        model_state["tokenizer"] = None
        model_state["model_path"] = None
        model_state["adapter_path"] = None
        gc.collect()
        torch.cuda.empty_cache()
        logger.info("Model unloaded")
    else:
        logger.info("No model to unload")
    
    return {"status": "unloaded"}

@app.post("/chat")
async def chat(request: ChatRequest):
    global pending_requests
    
    if model_state["model"] is None:
        raise HTTPException(status_code=400, detail="No model loaded. Call /load first.")

    # P0-FIX: Use asyncio.Lock to protect inference process
    # Increment pending count
    pending_requests += 1
    logger.info(f"Chat request queued. Pending: {pending_requests}")
    
    try:
        # Wait to acquire lock - other requests will wait here without blocking event loop
        async with inference_lock:
            pending_requests -= 1
            logger.info(f"Chat request started. Pending: {pending_requests}")
            
            model = model_state["model"]
            tokenizer = model_state["tokenizer"]

            # Prepare Chat Template
            inputs = tokenizer.apply_chat_template(
                request.messages,
                add_generation_prompt=True,
                return_tensors="pt"
            ).to(model.device)

            streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
            
            generation_kwargs = dict(
                input_ids=inputs,
                streamer=streamer,
                max_new_tokens=request.max_tokens,
                temperature=request.temperature,
                do_sample=True,
                top_p=0.9
            )

            thread = Thread(target=model.generate, kwargs=generation_kwargs)
            thread.start()

            # Collect all generated tokens (within lock)
            tokens = []
            try:
                for token in streamer:
                    if token:
                        tokens.append(token)
            except Exception as e:
                logger.error(f"Generation error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
            
            thread.join()  # Ensure generation completes
            
            logger.info(f"Chat request completed. Generated {len(tokens)} tokens.")

        # After lock release, return results in streaming fashion
        async def response_generator():
            for token in tokens:
                yield f"data: {json.dumps({'token': token})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

        return StreamingResponse(response_generator(), media_type="text/event-stream")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Inference error: {str(e)}")
        pending_requests = max(0, pending_requests - 1)  # Ensure count is correct
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
