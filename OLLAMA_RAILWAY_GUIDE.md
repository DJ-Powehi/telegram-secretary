# Running Ollama on Railway - Guide

## ⚠️ Important Considerations

### Challenges:
1. **Resource Intensive**: Ollama requires significant CPU/RAM (ideally GPU)
2. **Cost**: Railway charges per resource usage - running Ollama continuously can be expensive
3. **Performance**: LLM inference is slow on CPU-only (Railway doesn't offer GPU)
4. **Model Size**: `llama3.2:3b` is small but still needs ~2-4GB RAM

### Cost Estimate:
- Railway Hobby Plan: $5/month credit
- Running Ollama 24/7: ~$10-30/month (depending on usage)
- **Total**: ~$15-35/month (vs $5/month without Ollama)

## ✅ Option 1: Run Ollama on Railway (Possible but Expensive)

### Step 1: Add Ollama Service to Railway

1. In your Railway project, click "+ New"
2. Select "Empty Service"
3. Name it: `ollama-service`
4. Add this to `railway.json` or configure manually:

```json
{
  "services": [
    {
      "name": "telegram-bot",
      "build": { "builder": "NIXPACKS" },
      "deploy": { "startCommand": "python main.py" }
    },
    {
      "name": "ollama-service",
      "build": { "builder": "NIXPACKS" },
      "deploy": { 
        "startCommand": "ollama serve",
        "healthcheckPath": "/api/tags"
      }
    }
  ]
}
```

### Step 2: Install Ollama in Railway

Create `nixpacks.toml` or use build script:

```bash
# In Railway build command:
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2:3b
ollama serve
```

### Step 3: Configure Bot to Use Railway Ollama

Set environment variable in Railway:
```
OLLAMA_HOST=http://ollama-service:11434
```

**Note**: Railway services can communicate via service names as hostnames.

### Step 4: Update Code to Allow Railway Internal Network

We need to update the security check to allow Railway's internal networking.

## ✅ Option 2: Run Ollama Locally (Recommended)

Keep Ollama on your local machine or dedicated server:

1. **Local Machine**: Run `ollama serve` locally
2. **Expose via ngrok/tunneling**: Make it accessible to Railway
3. **Use Railway's public URL**: If you expose Ollama publicly (less secure)

**Security Note**: Exposing Ollama publicly is less secure. Better to keep it local.

## ✅ Option 3: Disable Ollama (Simplest)

The bot works perfectly without Ollama - it just won't generate topic summaries.

- Messages still captured ✅
- Warnings still work ✅
- Classification still works ✅
- Summaries still work ✅
- Topic summaries: ❌ (optional feature)

## 🎯 Recommendation

**For Client Deployment**: 
- **Option 3 (Disable Ollama)** is best for Railway
- Keeps costs low ($5/month)
- All core features work
- Topic summaries are nice-to-have, not essential

**If Client Wants AI Summaries**:
- Run Ollama on a separate VPS (DigitalOcean, Hetzner) - $5-10/month
- Or use cloud LLM API (OpenAI, Anthropic) - pay-per-use

## 📝 Code Update Needed

We should update the code to:
1. Allow Railway internal network connections
2. Make Ollama truly optional (graceful degradation)
3. Support both localhost and Railway service URLs
