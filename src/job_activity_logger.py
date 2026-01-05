import requests
import logging
from datetime import date
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()


class JobActivityLogger:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_url = os.getenv('WBL_API_URL', '').rstrip('/')
        if not self.api_url.endswith('/api'): self.api_url += '/api'
        self.api_token = os.getenv('WBL_API_TOKEN', '')
        self.wbl_creds = (os.getenv('WBL_EMAIL', ''), os.getenv('WBL_PASSWORD', ''))
        self.job_unique_id = os.getenv('JOB_UNIQUE_ID', 'vendors_mass_email_sender')
        self.employee_id = int(os.getenv('EMPLOYEE_ID', '411'))
        self.selected_candidate_id = int(os.getenv('SELECTED_CANDIDATE_ID', '570'))

        if not self.api_token and all(self.wbl_creds): self._auto_login()
        self.headers = {"Authorization": f"Bearer {self.api_token}", "Content-Type": "application/json"}

    def log_activity(self, activity_count, notes="", candidate_id=0, activity_date=None):
        if not self.api_token: return False
        
        job_type_id = self._get_job_type_id()
        if not job_type_id: return False

        payload = {
            "job_id": job_type_id,
            "employee_id": self.employee_id,
            "activity_count": activity_count,
            "candidate_id": candidate_id or self.selected_candidate_id or None,
            "notes": notes,
            "activity_date": activity_date or date.today().isoformat()
        }

        try:
            response = requests.post(f"{self.api_url}/job_activity_logs", json=payload, headers=self.headers)
            response.raise_for_status()
            self.logger.info(f"Activity logged: {activity_count} apps")
            return True
        except Exception as e:
            self.logger.error(f"Logging failed: {e}")
            return False

    def _auto_login(self):
        try:
            url = f"{self.api_url}/login" if 'localhost' not in self.api_url else self.api_url.replace('/api', '/api/login')
            response = requests.post(url, data={"username": self.wbl_creds[0], "password": self.wbl_creds[1]}, headers={"Content-Type": "application/x-www-form-urlencoded"})
            response.raise_for_status()
            token = response.json().get("access_token")
            if token:
                self.api_token = token
                self._update_env_token(token)
        except Exception as e: self.logger.error(f"Auto-login failed: {e}")

    def _update_env_token(self, token):
        try:
            with open(".env", 'r') as f: content = f.read()
            if "WBL_API_TOKEN=" in content:
                content = content.replace(f"WBL_API_TOKEN={os.getenv('WBL_API_TOKEN', '')}", f"WBL_API_TOKEN={token}")
            else: content += f"\nWBL_API_TOKEN={token}\n"
            with open(".env", 'w') as f: f.write(content)
        except Exception as e: self.logger.error(f"Failed to update .env: {e}")

    def _get_job_type_id(self):
        try:
            response = requests.get(f"{self.api_url}/job-types", headers=self.headers)
            if response.status_code == 401 and all(self.wbl_creds):
                self._auto_login()
                self.headers["Authorization"] = f"Bearer {self.api_token}"
                response = requests.get(f"{self.api_url}/job-types", headers=self.headers)
            
            response.raise_for_status()
            for jt in response.json():
                if jt.get('unique_id') == self.job_unique_id: return jt.get('id')
        except: pass
        return None

def log_job_activity(count, notes=""):
    return JobActivityLogger().log_activity(count, notes)
