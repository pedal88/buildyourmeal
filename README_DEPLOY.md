# Deployment Guide

This guide describes how to deploy the **Build Your Meal** application to **Google Cloud Run** and initialize the production **Cloud SQL** database.

## Prerequisites
1.  **Google Cloud Project**: You need an active project ID.
2.  **Tooling**:
    *   **Google Cloud SDK (`gcloud`)**: [Install Guide](https://cloud.google.com/sdk/docs/install). Run `gcloud auth login` and `gcloud config set project [PROJECT_ID]`.
    *   **Docker**: Installed and running locally.
3.  **APIs Enabled**: Cloud Run, Cloud Build, Cloud SQL Admin.
4.  **Infrastructure**:
    *   **GCS Bucket**: `buildyourmeal-assets` (Created in Phase 1).
    *   **Cloud SQL Instance**: Postgres 15+ (Created manually in Console).
    *   **Database**: Created inside the instance (e.g., `kitchen_db`).
    *   **User**: Created inside the instance (e.g., `appuser` with password).

## 1. Deploy Application

Run the deployment script. It will build the container and deploy it to Cloud Run.

```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh [YOUR_PROJECT_ID]
```

You will be prompted for:
*   **Database User**: `appuser`
*   **Database Password**: `[HIDDEN]`
*   **Database Name**: `kitchen_db`
*   **Connection Name**: `project-id:region:instance-name`

**Finding the Connection Name**:
1.  Go to Google Cloud Console -> SQL.
2.  Click on your instance.
3.  Copy the "Connection name" from the Overview page.

## 2. Initialize Production Database

After deployment (or before), you need to create the tables in the empty production database.

1.  Export the necessary credentials in your local shell (the script uses them to connect securely via proxy):
    ```bash
    export INSTANCE_CONNECTION_NAME='project-id:region:instance-name'
    export DB_USER='appuser'
    export DB_PASS='secret'
    export DB_NAME='kitchen_db'
    export GOOGLE_APPLICATION_CREDENTIALS='/path/to/key.json' # If not using gcloud auth
    ```

2.  Run the initialization script:
    ```bash
    python scripts/init_prod_db.py
    ```

3.  Confirm the prompt. The script will use the Google Cloud SQL Connector to safelytunnel to your instance and run `db.create_all()`.

## 3. Verify Deployment

1.  Open the **Service URL** provided by the deployment script output.
2.  Navigate to `/pantry`.
3.  If successful, the app should load (likely empty/default data) without errors.
