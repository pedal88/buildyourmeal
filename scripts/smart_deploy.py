#!/usr/bin/env python3
import subprocess
import sys
import time
import json
import os
import getpass
import shutil

# Configuration
SERVICE_NAME = "bym-app"
REGION = "us-central1"
GCS_BUCKET = "buildyourmeal-assets"
TEMP_BUILD_DIR = "/tmp/bym_build_staging"

# Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"

def print_step(msg):
    print(f"\n{BOLD}{GREEN}>>> {msg}{RESET}")

def run_command(cmd, shell=False, capture_output=True, text=True, cwd=None):
    """Runs a command and returns the result."""
    try:
        result = subprocess.run(
            cmd, 
            shell=shell, 
            capture_output=capture_output, 
            text=text, 
            check=True,
            cwd=cwd
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"{RED}Command failed: {e}{RESET}")
        if e.stderr:
            print(f"{RED}Error output: {e.stderr}{RESET}")
        raise

def stage_project():
    """Copies the project to a temp dir to avoid OneDrive locking/slow uploads."""
    print_step(f"Staging project to {TEMP_BUILD_DIR}")
    print(f"{YELLOW}   (Bypassing OneDrive & Ignoring large files...){RESET}")
    
    if not os.path.exists(TEMP_BUILD_DIR):
        os.makedirs(TEMP_BUILD_DIR)
        
    # Construct rsync command to mirror project but exclude junk
    # This acts as a robust .gcloudignore enforcer before we even touch gcloud
    cmd = [
        "rsync", "-a", "--delete",
        "--exclude", ".git",
        "--exclude", "venv",
        "--exclude", "google-cloud-sdk",
        "--exclude", "*.tar.gz",
        "--exclude", "*.zip",
        "--exclude", "__pycache__",
        "--exclude", ".DS_Store",
        "--exclude", "temp_video", 
        "--exclude", "temp_ingredients_for_Mapping",
        "--exclude", "static/pantry",
        "--exclude", "static/recipes",
        ".", 
        TEMP_BUILD_DIR
    ]
    
    run_command(cmd)
    return TEMP_BUILD_DIR

def check_staged_size(cwd):
    """Checks the size of the STAGED directory."""
    try:
        output = run_command(["du", "-sh", "."], capture_output=True, cwd=cwd)
        size_str = output.split()[0]
        print(f"   Staged Context Size: {BOLD}{size_str}{RESET} (Should be small, e.g. <100M)")
    except Exception as e:
        print(f"{YELLOW}Could not check size: {e}{RESET}")

def get_secrets():
    print_step("Configuration: credentials")
    
    if len(sys.argv) > 1:
        project_id = sys.argv[1]
    else:
        print(f"Usage: {sys.argv[0]} [PROJECT_ID]")
        project_id = input("Enter PROJECT_ID: ").strip()
        
    print(f"Target Project: {BOLD}{project_id}{RESET}")
    
    db_user = input("Enter Database User (e.g. appuser) [postgres]: ").strip() or "postgres"
    db_pass = getpass.getpass("Enter Database Password: ").strip()
    
    db_name = input("Enter Database Name (e.g. kitchen_db) [postgres]: ").strip() or "postgres"
    
    conn_name = input("Enter Instance Connection Name (project:region:instance): ").strip()
    if not conn_name:
        print(f"{RED}Error: Connection name required.{RESET}")
        sys.exit(1)
        
    api_key = getpass.getpass("Enter GOOGLE_API_KEY: ").strip()
    
    return {
        "PROJECT_ID": project_id,
        "DB_USER": db_user,
        "DB_PASS": db_pass,
        "DB_NAME": db_name,
        "INSTANCE_CONNECTION_NAME": conn_name,
        "GOOGLE_API_KEY": api_key
    }

def monitor_build(build_id, project_id):
    """Polls build status and prints a live dashboard."""
    print_step(f"Supervising Build: {build_id}")
    
    start_time = time.time()
    
    while True:
        try:
            # Fetch build details
            cmd = [
                "gcloud", "builds", "describe", build_id,
                "--project", project_id,
                "--format", "json"
            ]
            output = run_command(cmd)
            build_data = json.loads(output)
            
            status = build_data.get("status", "UNKNOWN")
            steps = build_data.get("steps", [])
            
            # Find current step
            current_step_name = "Initializing"
            for step in steps:
                s_status = step.get("status")
                if s_status == "WORKING":
                    current_step_name = step.get("id") or step.get("name")
                    break
                if s_status == "FAILURE":
                    current_step_name = step.get("id") or step.get("name")
                    break
            
            elapsed = int(time.time() - start_time)
            mins, secs = divmod(elapsed, 60)
            timer = f"{mins:02}:{secs:02}"
            
            # Interactive Line
            status_color = GREEN if status == "SUCCESS" else (RED if status in ["FAILURE", "TIMEOUT"] else YELLOW)
            
            sys.stdout.write(f"\r{BOLD}[Time: {timer}]{RESET} Status: {status_color}{status}{RESET} | Step: {current_step_name}                             ")
            sys.stdout.flush()
            
            if status in ["SUCCESS", "FAILURE", "TIMEOUT", "CANCELLED"]:
                print() # Newline
                return status == "SUCCESS"
                
            time.sleep(3)
            
        except KeyboardInterrupt:
            print(f"\n{YELLOW}Supervision paused. Build {build_id} continues in background.{RESET}")
            sys.exit(0)
        except Exception as e:
            # Tolerant polling
            time.sleep(3)

def main():
    # 1. Get Secrets First (so we don't stage if user cancels)
    secrets = get_secrets()
    project_id = secrets["PROJECT_ID"]
    
    # 2. Stage Code
    staging_dir = stage_project()
    check_staged_size(staging_dir)
    
    # 3. Submit Build (From Staging Dir)
    print_step("Submitting Build (Async)...")
    
    image_tag = f"gcr.io/{project_id}/{SERVICE_NAME}"
    
    # Note: We must create a minimal .gcloudignore in staging or ensure gcloud defaults are sanity checked.
    # Since rsync cleaned it, we simply rely on the folder content being clean.
    # We can create a .gcloudignore in staging to be redundant/safe.
    with open(os.path.join(staging_dir, ".gcloudignore"), "w") as f:
        f.write(".git\nvenv\ngoogle-cloud-sdk\n*.tar.gz\n")

    submit_cmd = [
        "gcloud", "builds", "submit",
        "--tag", image_tag,
        "--project", project_id,
        "--async",
        "--format", "value(id)"
    ]
    
    try:
        # EXECUTE IN STAGING DIR
        build_id = run_command(submit_cmd, cwd=staging_dir)
        print(f"Build ID: {BOLD}{build_id}{RESET}")
    except Exception:
        print(f"{RED}Failed to submit build.{RESET}")
        sys.exit(1)
        
    # 4. Monitor Build
    success = monitor_build(build_id, project_id)
    
    if not success:
        print(f"{RED}Build Failed. Run 'gcloud builds log {build_id}' to see details.{RESET}")
        sys.exit(1)
        
    print(f"{GREEN}Build Successful!{RESET}")
    
    # 5. Deploy (Can run from anywhere, checks cloud registry)
    print_step("Deploying to Cloud Run...")
    
    deploy_cmd = [
        "gcloud", "run", "deploy", SERVICE_NAME,
        "--image", image_tag,
        "--project", project_id,
        "--region", REGION,
        "--platform", "managed",
        "--allow-unauthenticated",
        "--add-cloudsql-instances", secrets["INSTANCE_CONNECTION_NAME"],
        "--set-env-vars", "DB_BACKEND=cloudsql",
        "--set-env-vars", f"GOOGLE_API_KEY={secrets['GOOGLE_API_KEY']}",
        "--set-env-vars", "STORAGE_BACKEND=gcs",
        "--set-env-vars", f"GCS_BUCKET_NAME={GCS_BUCKET}",
        "--set-env-vars", f"INSTANCE_CONNECTION_NAME={secrets['INSTANCE_CONNECTION_NAME']}",
        "--set-env-vars", f"DB_USER={secrets['DB_USER']}",
        "--set-env-vars", f"DB_PASS={secrets['DB_PASS']}",
        "--set-env-vars", f"DB_NAME={secrets['DB_NAME']}",
        "--set-env-vars", "FLASK_DEBUG=0"
    ]
    
    try:
        # Run deploy (stream output)
        subprocess.run(deploy_cmd, check=True)
        print(f"\n{BOLD}{GREEN}>>> Deployment Complete! <<<{RESET}")
    except subprocess.CalledProcessError:
        print(f"\n{RED}Deployment Failed.{RESET}")
        sys.exit(1)

if __name__ == "__main__":
    main()
