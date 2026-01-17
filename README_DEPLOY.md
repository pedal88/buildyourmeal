# 🚀 Deployment Guide (CI/CD)

**Current Status:** Automated via GitHub Actions

> [!WARNING]
> **DEVELOPMENT WARNING:** Do not store this project in OneDrive/Google Drive. File locking causes build failures. Use a local directory (e.g., `~/Projects`).

## 1. The New Workflow
Deployment is now **fully automated**. You do not need to run `gcloud` commands manually.

1.  **Develop Locally:** Make changes in your local `~/Projects/bym2026` folder.
2.  **Commit & Push:**
    ```bash
    git add .
    git commit -m "feat: your amazing change"
    git push origin main
    ```
3.  **Watch it Fly:**
    *   Go to **GitHub -> Actions** tab.
    *   Watch the pipeline: Lint -> Security Scan -> Build -> Migrate DB -> Deploy.
    *   ✅ **Success:** App updates automatically.
    *   ❌ **Failure:** Pipeline stops. Old version keeps running.

## 2. Prerequisites (One-Time Setup)
This pipeline relies on **Workload Identity Federation (WIF)** for keyless security.

1.  **Run Setup Script:**
    (If not done yet) Run `scripts/setup_wif.sh` in Cloud Shell.

2.  **Set GitHub Secrets:**
    Add these to your repository settings:
    *   `PROJECT_ID`: `gen-lang-client-0770637546`
    *   `WIF_PROVIDER`: (Output from script)
    *   `WIF_SERVICE_ACCOUNT`: (Output from script)

## 3. Troubleshooting
*   **Pipeline Failed?** Check the Logs in GitHub Actions.
*   **Database Error?** Check the "Execute Migration Job" step logs.
*   **Manual Deployment (Emergency Only):**
    *   See `README_CLOUD_DEPLOYMENT.md` for the emergency Cloud Shell method.
    *   **Do not use local `scripts/deploy.sh`** (It is deprecated).

## 4. History
*   **2026-01-17:** Transitioned from manual OneDrive scripts to GitHub Actions.
*   **Deprecated:** `scripts/deploy.sh`, `scripts/smart_deploy.py`.
