# Configuration

Configure Praxis using environment variables.

## Required (for inference.py)

| Variable | Description | Example |
|---|---|---|
| `HF_TOKEN` | HuggingFace API key used as the OpenAI client API key | `hf_abc123...` |
| `API_BASE_URL` | LLM inference endpoint (OpenAI-compatible) | `https://router.huggingface.co/v1` |
| `MODEL_NAME` | Model identifier | `Qwen/Qwen2.5-72B-Instruct` |

## Optional (server tuning)

| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Server log level: `DEBUG` · `INFO` · `WARNING` · `ERROR` |
| `PORT` | `7860` | Server port (HF Spaces requires `7860`) |

## Setting Variables

**Locally:**
```bash
export HF_TOKEN=hf_your_token_here
export API_BASE_URL=https://router.huggingface.co/v1
export MODEL_NAME=Qwen/Qwen2.5-72B-Instruct
python inference.py
```

**Docker:**
```bash
docker run -p 7860:7860 \
  -e HF_TOKEN=hf_your_token_here \
  -e API_BASE_URL=https://router.huggingface.co/v1 \
  -e MODEL_NAME=Qwen/Qwen2.5-72B-Instruct \
  praxis-env
```

**HuggingFace Spaces:**  
Add these as Space Secrets in your HF Space settings. They are injected automatically at runtime.

> ⚠️ Never commit API keys to the repository. Always use environment variables or HF Space Secrets.
