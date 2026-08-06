# Railway Deployment Guide

## OpenAI API Connection Issues on Railway

If you see `✗ OpenAI API connection failed: APIConnectionError` in Railway logs:

### ✅ **Solution Steps:**

#### 1. **Verify API Key in Railway Dashboard**
- Go to Railway Dashboard → Your Project → Service
- Click **Variables** tab
- Ensure `OPENAI_API_KEY` is set correctly
- Key should start with `sk-` or `sk-proj-`

#### 2. **Check API Key Status**
- Visit https://platform.openai.com/api-keys
- Verify your key is **Active** (not revoked)
- Check if you have **available credits/quota**
- Confirm the key has proper permissions

#### 3. **Common Railway Issues:**

**Issue**: Environment variable not loaded
- **Fix**: Redeploy the service after adding variables
- Railway requires redeployment for new env vars to take effect

**Issue**: OpenAI API key expired or invalid
- **Fix**: Generate a new key at https://platform.openai.com/api-keys
- Update in Railway dashboard
- Redeploy

**Issue**: OpenAI API quota exceeded
- **Fix**: Check usage at https://platform.openai.com/usage
- Add billing method or upgrade plan
- Or switch to Azure OpenAI (see below)

#### 4. **Alternative: Use Azure OpenAI**

If OpenAI.com is blocked or unavailable, use Azure OpenAI:

```bash
# In Railway Variables, add:
USE_AZURE_OPENAI=true
AZURE_OPENAI_API_KEY=your_azure_key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o-mini
```

---

## Current Issue Analysis

Based on your logs:
- ✓ DNS resolution works (can find api.openai.com)
- ✗ SSL handshake times out

**Most Likely Causes:**
1. **API Key not set in Railway Variables** (most common)
2. **API Key is invalid or expired**
3. **OpenAI API quota exceeded** (no credits)

**Recommended Action:**
1. Double-check `OPENAI_API_KEY` in Railway dashboard
2. Verify key is active at https://platform.openai.com/api-keys
3. Check usage/billing at https://platform.openai.com/usage
4. Redeploy after confirming env vars

---

## Testing Locally vs Railway

**Local**: Uses `.env` file
**Railway**: Uses Railway Variables (dashboard)

Make sure both have the same valid API key!
