#!/bin/bash
set -e

# Configuration
PROJECT_ID="gen-lang-client-0770637546"
REGION="us-central1"
SERVICE_NAME="bym-app"
REPO="pedal88/buildyourmeal" # Detected from git remote

SA_NAME="github-actions-sa"
POOL_NAME="github-actions-pool"
PROVIDER_NAME="github-actions-provider"

echo "=== Starting WIF Setup for $REPO ==="

# 1. Create Service Account
if gcloud iam service-accounts describe "${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    echo "Service Account $SA_NAME already exists."
else
    echo "Creating Service Account $SA_NAME..."
    gcloud iam service-accounts create "${SA_NAME}" \
      --description="Service Account for GitHub Actions CI/CD" \
      --display-name="GitHub Actions SA" \
      --project="${PROJECT_ID}"
fi
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# 2. Grant Roles
echo "Granting roles to $SA_EMAIL..."
ROLES=("roles/run.admin" "roles/storage.admin" "roles/iam.serviceAccountUser" "roles/artifactregistry.admin" "roles/cloudbuild.builds.editor")
for ROLE in "${ROLES[@]}"; do
    gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
      --member="serviceAccount:${SA_EMAIL}" \
      --role="${ROLE}" \
      --condition=None \
      --quiet >/dev/null
done

# 3. Create Workload Identity Pool
if gcloud iam workload-identity-pools describe "${POOL_NAME}" --project="${PROJECT_ID}" --location="global" >/dev/null 2>&1; then
    echo "Pool $POOL_NAME already exists."
else
    echo "Creating Workload Identity Pool $POOL_NAME..."
    gcloud iam workload-identity-pools create "${POOL_NAME}" \
      --project="${PROJECT_ID}" \
      --location="global" \
      --display-name="GitHub Actions Pool"
fi

# 4. Create Provider
if gcloud iam workload-identity-pools providers describe "${PROVIDER_NAME}" --project="${PROJECT_ID}" --location="global" --workload-identity-pool="${POOL_NAME}" >/dev/null 2>&1; then
    echo "Provider $PROVIDER_NAME already exists."
else
    echo "Creating Workload Identity Provider $PROVIDER_NAME..."
    gcloud iam workload-identity-pools providers create-oidc "${PROVIDER_NAME}" \
      --project="${PROJECT_ID}" \
      --location="global" \
      --workload-identity-pool="${POOL_NAME}" \
      --display-name="GitHub Actions Provider" \
      --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
      --attribute-condition="assertion.repository=='${REPO}'" \
      --issuer-uri="https://token.actions.githubusercontent.com"
fi

# 5. Bind Repo to Service Account
echo "Binding GitHub Repo $REPO to Service Account..."
POOL_ID=$(gcloud iam workload-identity-pools describe "${POOL_NAME}" --project="${PROJECT_ID}" --location="global" --format="value(name)")
gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
  --project="${PROJECT_ID}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/${POOL_ID}/attribute.repository/${REPO}" \
  --condition=None \
  --quiet >/dev/null

# 6. Output Secrets
PROVIDER_ID=$(gcloud iam workload-identity-pools providers describe "${PROVIDER_NAME}" --project="${PROJECT_ID}" --location="global" --workload-identity-pool="${POOL_NAME}" --format="value(name)")

echo ""
echo "=== SETUP COMPLETE ==="
echo "Please add the following secrets to your GitHub Repository ($REPO):"
echo ""
echo "WIF_PROVIDER: $PROVIDER_ID"
echo "WIF_SERVICE_ACCOUNT: $SA_EMAIL"
echo ""
