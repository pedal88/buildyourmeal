# Top Commands Cheat Sheet 🚀

Here are the most frequently used commands for developing and deploying the AI Kitchen.

## 1. Run Application Locally 💻
Starts the development server on your machine.
```bash
# Make sure your venv is active or use the direct path
./venv/bin/python app.py
```
*Access at: http://127.0.0.1:8000*

## 2. Deploy to Production ☁️
Builds the docker image and deploys it to Google Cloud Run.
```bash
# Replace [PROJECT_ID] with your ID (e.g., bym-app-287448924512)
./scripts/deploy.sh [PROJECT_ID]
```

## 3. Push Changes to Git 🐙
Saves your code changes to the history and uploads them to the repository.
```bash
git add .
git commit -m "Describe your changes here"
git push
```

## 4. View Production Logs 📋
Check the live logs from the Cloud Run application to debug errors.
```bash
gcloud run services logs read bym-app --region us-central1 --limit 20
```

## 5. Connect to Prod Database (Safe Shell) 🗄️
Open a Python shell connected to the production Cloud SQL database.
```bash
# Login first
gcloud auth application-default login

# Export Connection Config (Mac/Linux)
export DB_BACKEND=cloudsql
export INSTANCE_CONNECTION_NAME=$(gcloud sql instances list --format="value(connectionName)" --filter="state:RUNNABLE" --limit=1)

# Run Shell
./venv/bin/python -c "from app import app, db; from database.models import *; print('Connected to Prod DB'); import code; code.interact(local=locals())"
```
