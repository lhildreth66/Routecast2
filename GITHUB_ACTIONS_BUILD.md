# GitHub Actions Build Setup

## FREE Android Builds with GitHub Actions

This repository uses GitHub Actions to build Android apps **for FREE** using `eas build --local`. This runs builds on GitHub's free runners instead of Expo's paid cloud service.

### Benefits:
- ✅ **FREE unlimited builds** (within GitHub's 2000 min/month free tier)
- ✅ No EAS cloud build credits charged
- ✅ Still uses EAS CLI tools and configurations
- ✅ Automatic builds on every push to `main`
- ✅ Manual builds via workflow dispatch

### Setup Instructions:

#### 1. Get your Expo Token
```bash
# Login to Expo (if not already)
npx expo login

# Generate a token
npx expo token:create
```

Copy the generated token.

#### 2. Add Token to GitHub Secrets

1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `EXPO_TOKEN`
5. Value: Paste your Expo token
6. Click **Add secret**

#### 3. Trigger a Build

**Automatic:** Push any changes to `main` branch that affect `frontend/` directory

**Manual:**
1. Go to **Actions** tab
2. Select **Build Android App** workflow
3. Click **Run workflow**
4. Select `main` branch
5. Click **Run workflow**

#### 4. Download the AAB

After the build completes:
1. Go to the workflow run
2. Scroll to **Artifacts** section
3. Download the `android-release-XXXXXX` artifact
4. Extract the `.aab` file
5. Upload to Google Play Console

### Cost Comparison:

| Service | Cost | Notes |
|---------|------|-------|
| **EAS Build (Cloud)** | $29/month | After free tier exhausted |
| **GitHub Actions** | **FREE** | 2000 minutes/month free tier |
| Android Build Time | ~15-20 min | Well within free tier |

### Workflow File:

The workflow is configured in `.github/workflows/build-android.yml`

Key differences from cloud builds:
- Uses `--local` flag: `eas build --local --platform android`
- Runs on GitHub's `ubuntu-latest` runners
- Requires `EXPO_TOKEN` secret for authentication
- Uploads `.aab` as GitHub artifact

### Troubleshooting:

**Build fails with "EXPO_TOKEN not found":**
- Make sure you added the secret in repository settings
- Secret name must be exactly `EXPO_TOKEN`

**Build fails with Java errors:**
- Workflow uses Java 17 (required for newer Android builds)
- This is automatically installed in the workflow

**Can't find the AAB:**
- Check the workflow run logs
- Look in the "Artifacts" section of the workflow run
- AABs are retained for 30 days

**Want to build on-demand:**
- Use workflow dispatch (manual trigger)
- Or push to `main` branch

### Version Management:

Before triggering a build:
```bash
# Bump version using the script
./scripts/bump-version.sh 1.0.109 109

# Commit and push
git add frontend/app.json frontend/android/app/build.gradle
git commit -m "Bump version to 1.0.109"
git push origin main
```

The workflow will automatically build the new version.
