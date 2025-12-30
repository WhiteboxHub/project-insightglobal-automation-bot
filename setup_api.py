import requests
import json
import os
from pathlib import Path

DEFAULT_API_URL = "https://whitebox-learning.com/api"
JOB_UNIQUE_ID = "leads_mass_email_sender"
ENV_FILE = ".env"

def run_setup():
    print("=" * 70)
    print(" WBL API SETUP FOR LEADS EMAIL SENDER")
    print("=" * 70)
    print("\nThis script will configure the API credentials for logging email activities.")
    print("=" * 70)

    # Step 1: Configuration Choice
    print("\n Step 1: Select Environment")
    print("-" * 70)
    print(f"1. Production (Default: {DEFAULT_API_URL})")
    print("2. Local (http://localhost:8000/api)")
    choice = input("\nSelect environment [1/2, default: 1]: ").strip() or "1"

    if choice == "2":
        api_url = "http://localhost:8000/api"
    else:
        api_url = DEFAULT_API_URL

    print("\n Step 2: Your Credentials")
    print("-" * 70)
    email = input("Enter your WBL email: ")
    password = input("Enter your WBL password: ")
    employee_id = input("Enter your Employee ID (e.g., 353): ").strip()

    while not employee_id:
        employee_id = input("Employee ID is required. Please enter it: ").strip()

    print("\n Step 3: Getting JWT Token")
    print("-" * 70)

    login_url = f"{api_url}/login"
    if "localhost" in api_url and not api_url.endswith("/api"):
        login_url = f"{api_url}/api/login"

    try:
        response = requests.post(
            login_url,
            data={
                "username": email,
                "password": password
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        response.raise_for_status()
        data = response.json()
        token = data.get("access_token")

        if not token:
            print(" ERROR: No access_token in response")
            return

        print(f" Token received: {token[:20]}...{token[-20:]}")

    except Exception as e:
        print(f" Login failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
             print(f"   Response: {e.response.text}")
        return

    print("\n Step 4: Updating .env File")
    print("-" * 70)

    try:
        env_content = ""
        if os.path.exists(ENV_FILE):
            with open(ENV_FILE, 'r') as f:
                env_content = f.read()
        else:
            env_content = f"""# WBL API Configuration
WBL_API_URL={api_url}
WBL_API_TOKEN={token}
JOB_UNIQUE_ID={JOB_UNIQUE_ID}
EMPLOYEE_ID={employee_id}
SELECTED_CANDIDATE_ID=0
"""

        def update_key(content, key, value):
            if f"{key}=" in content:
                return content.replace(f"{key}={content.split(f'{key}=')[1].split('\n')[0]}", f"{key}={value}")
            else:
                return content.rstrip() + f"\n{key}={value}\n"

        env_content = update_key(env_content, "WBL_API_URL", api_url)
        env_content = update_key(env_content, "WBL_API_TOKEN", token)
        env_content = update_key(env_content, "JOB_UNIQUE_ID", JOB_UNIQUE_ID)
        env_content = update_key(env_content, "EMPLOYEE_ID", employee_id)
        env_content = update_key(env_content, "SELECTED_CANDIDATE_ID", "0")

        with open(ENV_FILE, 'w') as f:
            f.write(env_content)

        print(f" Updated {ENV_FILE} with your API configuration.")

    except Exception as e:
        print(f" Failed to update .env: {e}")
        return

    print("\n Step 5: Verifying Job Type in Database")
    print("-" * 70)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    types_url = f"{api_url}/job-types"
    if "localhost" in api_url and not api_url.endswith("/api"):
        types_url = f"{api_url}/api/job-types"

    try:
        response = requests.get(types_url, headers=headers)
        response.raise_for_status()
        existing_jobs = response.json()

        job_exists = False
        for job in existing_jobs:
            if job.get('unique_id') == JOB_UNIQUE_ID:
                print(f" Job type already exists (ID: {job.get('id')})")
                job_exists = True
                break

        if not job_exists:
            print("Creating missing job type...")
            job_type_data = {
                "unique_id": JOB_UNIQUE_ID,
                "name": "Leads Mass Email Sender",
                "job_owner_id": int(employee_id),
                "description": "Automated mass email sender for leads outreach",
                "notes": "Sends bulk emails to leads and logs activity to WBL backend"
            }
            response = requests.post(types_url, json=job_type_data, headers=headers)
            response.raise_for_status()
            print(f" Job type created successfully.")

    except Exception as e:
        print(f"  Note: Could not verify/create job type via API: {e}")
        print("   If you have already run the SQL setup script, this is fine.")

    print("\n" + "=" * 70)
    print(" API SETUP COMPLETE!")
    print("=" * 70)
    print("\nYour email sender is now configured to log activities to the WBL API.")
    print(f"Linked to Employee ID: {employee_id}")
    print("\nNext step: Run 'python leads_mass_email_sender.py'")
    print("=" * 70)

if __name__ == "__main__":
    run_setup()
