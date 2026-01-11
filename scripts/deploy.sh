#!/bin/bash
set -e

# Configuration
SERVICE_NAME="bym-app"
REGION="us-central1" # Change as needed
GCS_BUCKET_NAME="buildyourmeal-assets" # Your verified bucket

# Colors
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}=== Build Your Meal Deployment Script ===${NC}"

# Check arguments
if [ -z "$1" ]; then
    echo "Usage: ./deploy.sh [PROJECT_ID]"
    exit 1
fi

PROJECT_ID=$1

# Prompt for Database Credentials (Secrets)
read -p "Enter Database User (e.g. appuser): " DB_USER
read -s -p "Enter Database Password: " DB_PASS
echo ""
read -p "Enter Database Name (e.g. kitchen_db): " DB_NAME
read -p "Enter Instance Connection Name (project:region:instance): " INSTANCE_CONNECTION_NAME

# Prompt for API Key
read -s -p "Enter GOOGLE_API_KEY: " GOOGLE_API_KEY
echo ""

echo -e "\n${GREEN}1. Building Container Image...${NC}"
gcloud builds submit --tag "gcr.io/$PROJECT_ID/$SERVICE_NAME"

echo -e "\n${GREEN}2. Deploying to Cloud Run...${NC}"
# Note: We pass secrets as env vars for simplicity here. 
# Production best practice is using Google Secret Manager integration.
gcloud run deploy "$SERVICE_NAME" \
  --image "gcr.io/$PROJECT_ID/$SERVICE_NAME" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --add-cloudsql-instances "$INSTANCE_CONNECTION_NAME" \
  --set-env-vars "DB_BACKEND=cloudsql" \
  --set-env-vars "GOOGLE_API_KEY=$GOOGLE_API_KEY" \
  --set-env-vars "STORAGE_BACKEND=gcs" \
  --set-env-vars "GCS_BUCKET_NAME=$GCS_BUCKET_NAME" \
  --set-env-vars "INSTANCE_CONNECTION_NAME=$INSTANCE_CONNECTION_NAME" \
  --set-env-vars "DB_USER=$DB_USER" \
  --set-env-vars "DB_PASS=$DB_PASS" \
  --set-env-vars "DB_NAME=$DB_NAME" \
  --set-env-vars "FLASK_DEBUG=0"

echo -e "\n${GREEN}Deployment Complete!${NC}"
