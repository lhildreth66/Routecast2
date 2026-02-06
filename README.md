# Routecast - Weather Along Your Route

Plan your road trip with real-time weather forecasts along your route. Get alerts for bad weather and AI-powered driving recommendations.

## Tech Stack

- **Frontend**: Expo (React Native) - iOS, Android, Web
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **APIs**: Mapbox (routing), NOAA (weather), Google Gemini (AI chat)

---

## Quick Start (Local Development)

### Prerequisites

- Node.js 18+ (LTS recommended)
- Python 3.10+
- MongoDB (local or Atlas)
- Yarn or npm
- Expo CLI (`npm install -g expo-cli`)

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/routecast.git
cd routecast
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your API keys (see Environment Variables below)

# Start the backend server
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

Backend will be running at `http://localhost:8001`

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
yarn install
# or: npm install

# Create .env file
cp .env.example .env
# Edit .env to point to your backend URL

# Start Expo development server
yarn start
# or: npx expo start
```

Frontend will be available at `http://localhost:3000` (web) or via Expo Go app (mobile)

---

## Environment Variables

### Backend (`/backend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `MONGO_URL` | Yes | MongoDB connection string |
| `DB_NAME` | Yes | Database name |
| `MAPBOX_ACCESS_TOKEN` | Yes | Mapbox API key for geocoding/routing |
| `GOOGLE_API_KEY` | Yes | Google API key for Gemini AI chat |
| `NOAA_USER_AGENT` | No | User agent for NOAA API requests |

### Frontend (`/frontend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `EXPO_PUBLIC_BACKEND_URL` | Yes | URL of your backend API server |

---

## Getting API Keys

### Mapbox
1. Go to https://account.mapbox.com/
2. Create an account or sign in
3. Go to Access tokens
4. Copy your default public token or create a new one

### Google Gemini
1. Go to https://makersuite.google.com/app/apikey
2. Create an API key
3. Copy the key to your `.env` file

### MongoDB Atlas (Optional - for cloud database)
1. Go to https://www.mongodb.com/atlas
2. Create a free cluster
3. Get your connection string from "Connect" > "Drivers"

---

## Render Deployment

### Backend Deployment

1. Create a new **Web Service** on Render
2. Connect your GitHub repository
3. Configure:
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn server:app --host 0.0.0.0 --port $PORT`
4. Add environment variables:
   - `MONGO_URL` (your MongoDB Atlas connection string)
   - `DB_NAME` (e.g., `routecast_db`)
   - `MAPBOX_ACCESS_TOKEN`
   - `GOOGLE_API_KEY`
5. Deploy!

### Frontend Deployment (Static Site)

Option 1: Build for web and deploy as static site
```bash
cd frontend
npx expo export --platform web
# Deploy the `dist` folder to Render Static Site
```

Option 2: For mobile apps, use EAS Build (see below)

---

## EAS Build for Google Play

### Prerequisites

1. Install EAS CLI: `npm install -g eas-cli`
2. Create an Expo account: https://expo.dev/
3. Login: `eas login`

### Configure EAS Project

```bash
cd frontend

# Initialize EAS project (first time only)
eas init

# Update app.json with your EAS project ID
```

### Build Android App Bundle (AAB)

```bash
# Production build for Google Play
eas build -p android --profile production
```

This creates an `.aab` file you can upload to Google Play Console.

### Important Notes for Google Play

1. **Package Name**: The app uses `com.routecast.app` - change this in `app.json` if needed
2. **Version**: Update `version` and `android.versionCode` in `app.json` for each release
3. **Signing**: EAS handles signing automatically, or you can provide your own keystore

---

## Project Structure

```
routecast/
├── backend/
│   ├── server.py          # FastAPI application
│   ├── requirements.txt   # Python dependencies
│   ├── .env.example       # Environment template
│   └── .env               # Your local environment (gitignored)
│
├── frontend/
│   ├── app/               # Expo Router pages
│   │   ├── index.tsx      # Home screen
│   │   ├── route.tsx      # Route details screen
│   │   └── _layout.tsx    # App layout
│   ├── assets/            # Images and icons
│   ├── app.json           # Expo configuration
│   ├── eas.json           # EAS Build configuration
│   ├── package.json       # Node dependencies
│   ├── .env.example       # Environment template
│   └── .env               # Your local environment (gitignored)
│
└── README.md              # This file
```

---

## Features

- 🗺️ **Route Planning**: Enter origin and destination for weather forecasts
- 🌦️ **Weather Data**: Real-time weather from NOAA for each waypoint
- ⚠️ **Alerts**: NWS weather alerts displayed along your route
- 🛣️ **Road Conditions**: AI-estimated road conditions (dry, wet, icy, snow)
- 📍 **Turn-by-Turn**: Mile markers with weather for each segment
- 🤖 **AI Chat**: Ask driving questions powered by Google Gemini
- 📡 **Weather Radar**: Live radar map with NWS warning overlays
- 🔔 **Notifications**: Push notifications for severe weather (mobile)

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/route/weather` | POST | Get weather along a route |
| `/api/geocode/suggestions` | GET | Autocomplete for locations |
| `/api/routes/history` | GET | Get recent routes |
| `/api/routes/favorites` | GET | Get favorite routes |
| `/api/chat` | POST | AI chat for driving questions |
| `/api/health` | GET | Health check |

---

## Troubleshooting

### Backend won't start
- Check MongoDB is running: `mongod --version`
- Verify all environment variables are set
- Check Python version: `python --version` (needs 3.10+)

### Frontend can't connect to backend
- Verify `EXPO_PUBLIC_BACKEND_URL` is correct
- Check backend is running on the expected port
- For mobile: use your computer's IP address, not `localhost`

### Windows curl returns 422 for `/api/route/weather`
On Windows **CMD**, line continuations with `\` break the request body. Use a single-line curl instead:

```
curl -i -X POST "https://routecast-backend.onrender.com/api/route/weather" -H "Content-Type: application/json" -d "{\"mode\":\"truck\",\"vehicle_type\":\"semi\",\"vehicle_height_ft\":13.5,\"vehicle_weight_lbs\":80000,\"vehicle_length_ft\":70,\"axle_count\":5,\"origin\":\"lat 41.8781 lon -87.6298\",\"destination\":\"41.7606 -87.6169\"}"
```

PowerShell version (cleaner):

```powershell
$body = @{
   mode = "truck"
   vehicle_type = "semi"
   vehicle_height_ft = 13.5
   vehicle_weight_lbs = 80000
   vehicle_length_ft = 70
   axle_count = 5
   origin = "lat 41.8781 lon -87.6298"
   destination = "41.7606 -87.6169"
} | ConvertTo-Json -Compress

curl -i -X POST "https://routecast-backend.onrender.com/api/route/weather" -H "Content-Type: application/json" -d $body
```

If the first line is not `HTTP/1.1 200 OK`, note the status and any `detail` field.

### EAS Build fails
- Run `eas diagnostics` to check setup
- Verify `app.json` has valid `expo.android.package`
- Check Expo account has correct permissions

---

## License

This project is owned by the repository owner. You are free to modify, deploy, and publish this application without restriction.

---

## Support

For issues or questions, please open a GitHub issue.
