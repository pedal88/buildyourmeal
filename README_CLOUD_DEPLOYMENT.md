Here is the `README.md` file summarizing our deployment journey. It is structured to provide both a conceptual overview and the hard technical details of how we moved "Build Your Meal" from your laptop to the cloud.

---

# Build Your Meal - Cloud Deployment Documentation

## 1. High-Level Overview: The Journey to the Cloud ☁️

This project was successfully migrated from a local development environment (running on a laptop with a simple file-based database) to a production-grade cloud infrastructure on Google Cloud Platform (GCP).

Think of this process like moving a restaurant from a home kitchen to a professional commercial space:

* **Packaging (The Suitcase):** We optimized the code upload. Originally, we tried to ship the entire "pantry" (your local virtual environment), which was too heavy (2.0 GB). We fixed this by telling Google to ignore local files and only build fresh from the recipe (`requirements.txt`), reducing the upload to just ~4 MB.
* **The New Kitchen (Cloud Run):** We rented a "Serverless" kitchen. This computer turns on when a user visits the website and turns off when they leave, saving money. It runs the application code.
* **The Professional Pantry (Cloud SQL):** We moved from storing data in a local file (`sqlite`) to a professional, scalable database server (PostgreSQL). This ensures data is safe, backed up, and accessible even if the app crashes or restarts.
* **Connecting the Utilities (IAM & Configuration):** The hardest part was connecting the Kitchen to the Pantry. We had to generate secure "keys" (IAM permissions) and tell the app exactly where the database lives (Environment Variables) so they could talk to each other securely.

---

## 2. Technical Deployment Architecture

This section details the specific steps, technologies, and configurations used to achieve the deployment.

### Phase 1: Artifact Optimization

**Objective:** Reduce build time and prevent upload timeouts.

* **Action:** configured `.gcloudignore` to exclude `venv/`, `__pycache__`, and local assets.
* **Result:** Reduced build context size from **2.0 GB to 4.7 MiB**.

### Phase 2: Infrastructure Provisioning

**Objective:** Set up the hosting environment.

* **Compute:** Enabled **Cloud Run API** to host the containerized Flask application.
* **Database:** Provisioned a **Cloud SQL (PostgreSQL)** instance named `buildyourmeal-db`.
* **Networking:** Enabled **Cloud SQL Admin API** to allow secure connectivity via the `cloud-sql-python-connector`.

### Phase 3: Dependency Management

**Objective:** Ensure the cloud environment mirrors the local requirements.

* **Server:** Switched from the development server (`flask run`) to a production WSGI server (**Gunicorn**).
* **Database Drivers:** Added `pg8000` (pure Python PostgreSQL driver) and `flask-sqlalchemy`.
* **Connector:** Added `cloud-sql-python-connector` to manage SSL certificates and IAM authentication automatically.

### Phase 4: Database Initialization (The "Hybrid" Operation)

**Objective:** Create the database schema (tables) in the Cloud SQL instance before the app launched.

* **Challenge:** The app cannot create tables if it crashes on startup due to missing tables.
* **Solution:** We ran a local Python script (`init_prod_db.py`) targeted at the remote Cloud infrastructure.
* **Authentication Fix:** We encountered IAM 403 errors. We resolved this by synchronizing the local Python Application Default Credentials (ADC) with the specific GCP project quota:
```bash
gcloud auth application-default login --update-adc
gcloud auth application-default set-quota-project [PROJECT_ID]

```


* **Configuration:** We explicitly forced the script to use the Cloud backend:
```bash
export DB_BACKEND=cloudsql
export INSTANCE_CONNECTION_NAME=[PROJECT:REGION:INSTANCE]
./venv/bin/python scripts/init_prod_db.py

```



### Phase 5: Production Deployment & Secrets

**Objective:** Launch the application and securely provide it with database credentials.

* **Deployment:** Used `gcloud builds submit` (via `deploy.sh`) to containerize the app based on the `Dockerfile` (or Cloud Buildpacks).
* **Environment Configuration:** The Cloud Run container is stateless. We injected the configuration via Environment Variables during the update:
* `DB_BACKEND`: `cloudsql`
* `DB_USER`: `postgres`
* `DB_PASS`: *[Secure Password]*
* `INSTANCE_CONNECTION_NAME`: `[PROJECT:REGION:INSTANCE]`


* **IAM Permissions:** We explicitly granted the **Service Account** (the identity running the app) the `roles/cloudsql.client` permission, allowing the "Robot" to access the database.

---

## 3. Key Technologies Used

| Technology | Role |
| --- | --- |
| **Python 3.12** | Core programming language. |
| **Flask** | Web framework. |
| **Gunicorn** | Production HTTP Server (WSGI). |
| **Google Cloud Run** | Serverless platform for hosting the container. |
| **Google Cloud SQL** | Managed PostgreSQL database service. |
| **SQLAlchemy** | ORM for database interactions. |
| **Cloud SQL Connector** | Python library for secure, password-less IAM database connections. |
| **Docker** | Containerization (handled implicitly by Google Cloud Build). |

---

## 4. Operational Commands (Cheatsheet)

**To Deploy Code Changes:**

```bash
./scripts/deploy.sh [PROJECT_ID]

```

**To Update Secrets/Config:**

```bash
gcloud run services update bym-app \
  --region us-central1 \
  --set-env-vars DB_PASS='YOUR_PASSWORD'

```

**To View Production Logs:**

```bash
gcloud run services logs read bym-app --region us-central1 --limit 20

```

**To Run Database Scripts Against Production (From Local):**

```bash
# 1. Login with ADC
gcloud auth application-default login

# 2. Export Config
export DB_BACKEND=cloudsql
export INSTANCE_CONNECTION_NAME=$(gcloud sql instances list --format="value(connectionName)" --filter="state:RUNNABLE" --limit=1)

# 3. Run Script
./venv/bin/python scripts/seed_db.py

```