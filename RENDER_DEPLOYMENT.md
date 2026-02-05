# Render Deployment Guide for Routecast

This guide shows how to deploy Routecast to Render with a stable backend API and optional web frontend.

---

## Quick Deploy (Render Blueprint)

If your repo contains `render.yaml`, Render can auto-deploy both services:

1. Go to https://dashboard.render.com/
2. Click **New** → **Blueprint**
3. Connect your GitHub repo
4. Render will detect `render.yaml` and create both services
5. Add your secret environment variables in the Render dashboard

---

## Manual Deployment

### Step 1: Deploy Backend

1. Go to https://dashboard.render.com/
2. Click **New** → **Web Service**
3. Connect your GitHub repository
4. Configure:

| Setting | Value |
|---------|-------|
| **Name** | `routecast-backend` |
| **Root Directory** | `backend` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn server:app --host 0.0.0.0 --port $PORT` |

5. Add Environment Variables:

| Key | Value | Notes |
|-----|-------|-------|
| `MONGO_URL` | `mongodb+srv://...` | Your MongoDB Atlas connection string |
| `DB_NAME` | `routecast_db` | Database name |
| `MAPBOX_ACCESS_TOKEN` | `pk.xxx` | Your Mapbox public token |
| `GOOGLE_API_KEY` | `AIza...` | Your Google Gemini API key |
| `PYTHON_VERSION` | `3.11.0` | Pin Python version |

6. Click **Create Web Service**
7. Wait for deploy to complete
8. Note your backend URL: `https://routecast-backend.onrender.com`

### Step 2: Test Backend Health

```bash
curl https://routecast-backend.onrender.com/api/health
# Should return: {"status":"healthy","timestamp":"..."}
```

### Step 3: Deploy Frontend (Optional - for Web)

For mobile apps, skip this and use EAS Build instead.

1. Click **New** → **Static Site** (or Web Service)
2. Connect your GitHub repository
3. Configure:

| Setting | Value |
|---------|-------|
| **Name** | `routecast-frontend` |
| **Root Directory** | `frontend` |
| **Build Command** | `yarn install && npx expo export --platform web` |
| **Publish Directory** | `dist` |

4. Add Environment Variables:

| Key | Value |
|-----|-------|
| `EXPO_PUBLIC_BACKEND_URL` | `https://routecast-backend.onrender.com` |
| `NODE_VERSION` | `18.19.0` |

5. Click **Create Static Site**

---

## CORS Configuration

The backend is already configured to accept requests from any origin:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

For production, you may want to restrict this to your specific domains.

---

## Environment Variables Summary

### Backend (Required)

| Variable | Description | Where to Get |
|----------|-------------|-------------|
| `MONGO_URL` | MongoDB connection string | https://mongodb.com/atlas |
| `DB_NAME` | Database name | Choose any name |
| `MAPBOX_ACCESS_TOKEN` | Mapbox API key | https://account.mapbox.com/ |
| `GOOGLE_API_KEY` | Google Gemini API key | https://makersuite.google.com/app/apikey |

### Frontend (Required)

| Variable | Description |
|----------|-------------|
| `EXPO_PUBLIC_BACKEND_URL` | Your Render backend URL |

---

## Troubleshooting

### Backend returns 502/503
- Check Render logs for startup errors
- Verify all environment variables are set
- Ensure `MONGO_URL` is correct and MongoDB Atlas allows connections from anywhere (0.0.0.0/0)

### Frontend can't reach backend
- Verify `EXPO_PUBLIC_BACKEND_URL` is set correctly
- Check CORS settings in backend
- Test backend health endpoint directly

### Cold starts are slow
- Render free tier spins down after 15 minutes of inactivity
- First request after idle takes 30-60 seconds
- Upgrade to paid plan for always-on instances

---

## Estimated Costs (Render)

| Service | Free Tier | Starter ($7/mo) |
|---------|-----------|----------------|
| Backend | 750 hrs/mo, sleeps after 15min | Always on |
| Frontend | Unlimited static hosting | N/A |

---

## Next Steps

After deploying:

1. Update `eas.json` production profile with your Render backend URL
2. Run `eas build -p android --profile production` to generate AAB
3. Upload AAB to Google Play Console
