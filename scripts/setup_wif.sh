#!/bin/bash
set -e

# Configuration
PROJECT_ID="gen-lang-client-0770637546"
GITHUB_REPO="pedal88/buildyourmeal"

# Generate a random suffix to avoid name collisions with old/deleted pools
RANDOM_SUFFIX=$((1000 + RANDOM % 9999))
POOL_NAME="github-pool-${RANDOM_SUFFIX}"
PROVIDER_NAME="github-provider"
SA_NAME="github-deployer"

echo "🚀 Setting up Workload Identity for repo: $GITHUB_REPO..."
echo "ℹ️  Using unique Pool ID: ${POOL_NAME}"

# 1. Enable Services
gcloud services enable iamcredentials.googleapis.com \
    cloudresourcemanager.googleapis.com \
    artifactregistry.googleapis.com \
    run.googleapis.com \
    --project "${PROJECT_ID}"

# 2. Create Service Account (Idempotent)
if ! gcloud iam service-accounts describe "${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" --project "${PROJECT_ID}" &>/dev/null; then
    gcloud iam service-accounts create "${SA_NAME}" \
        --display-name="GitHub Actions Deployer" \
        --project "${PROJECT_ID}"
    echo "✅ Service Account created"
else
    echo "ℹ️ Service Account already exists"
fi

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# 3. Grant IAM Roles
ROLES=(
    "roles/run.admin"
    "roles/storage.admin"
    "roles/artifactregistry.admin"
    "roles/cloudsql.client"
    "roles/iam.serviceAccountUser"
)

for role in "${ROLES[@]}"; do
    gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="${role}" \
        --condition=None \
        --quiet >/dev/null
    echo "  + Granted $role"
done

# 4. Create Workload Identity Pool (New Name)
gcloud iam workload-identity-pools create "${POOL_NAME}" \
    --location="global" \
    --display-name="GitHub Actions Pool ${RANDOM_SUFFIX}" \
    --project "${PROJECT_ID}"
echo "✅ WIF Pool created: ${POOL_NAME}"

# 5. Create Provider
gcloud iam workload-identity-pools providers create-oidc "${PROVIDER_NAME}" \
    --location="global" \
    --workload-identity-pool="${POOL_NAME}" \
    --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --project "${PROJECT_ID}"
echo "✅ WIF Provider created"

# 6. Bind GitHub Repo to Service Account
POOL_ID=$(gcloud iam workload-identity-pools describe "${POOL_NAME}" --location="global" --project "${PROJECT_ID}" --format="value(name)")

gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
    --project "${PROJECT_ID}" \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/${POOL_ID}/attribute.repository/${GITHUB_REPO}" \
    --quiet >/dev/null

echo "✅ Bound repo ${GITHUB_REPO} to Service Account"

# 7. Output Secrets
PROVIDER_ID=$(gcloud iam workload-identity-pools providers describe "${PROVIDER_NAME}" --location="global" --workload-identity-pool="${POOL_NAME}" --project "${PROJECT_ID}" --format="value(name)")

echo ""
echo "=========================================================="
echo "🎉 SETUP COMPLETE! Add these secrets to GitHub:"
echo "=========================================================="
echo "WIF_PROVIDER       : ${PROVIDER_ID}"
echo "WIF_SERVICE_ACCOUNT: ${SA_EMAIL}"
echo "PROJECT_ID         : ${PROJECT_ID}"
echo "=========================================================="
