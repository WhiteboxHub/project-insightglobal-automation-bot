# Insight Global Job Application Bot
# Multi-Candidate Automation

import os
import sys
import time
import random
import logging
import configparser
from datetime import datetime
from pathlib import Path
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from utils import setup_csv_logging
from dotenv import load_dotenv
from job_activity_logger import JobActivityLogger


class InsightGlobalJobBot:
    def __init__(self, config_path='config/settings.ini'):
        self.base_dir = Path(__file__).parent.parent
        load_dotenv()
        self.config = self._load_config(config_path)
        self._setup_logging()
        self.activity_logger = JobActivityLogger()
        self.driver = None
        self.wait = None
        self.current_candidate = None

    def _load_config(self, config_path):
        config = configparser.ConfigParser()
        config_file = self.base_dir / config_path
        config.read(config_file)
        return config

    def _setup_logging(self):
        log_dir = self.base_dir / 'logs'
        log_dir.mkdir(exist_ok=True)
        self.log_file = log_dir / f'jobbot_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

        log_level = getattr(logging, self.config.get('logging', 'log_level', fallback='INFO').upper(), logging.INFO)
        handlers = [logging.FileHandler(self.log_file), logging.StreamHandler(sys.stdout)]

        if self.config.getboolean('logging', 'csv_logging_enabled', fallback=True):
            try:
                handlers.append(setup_csv_logging(self.config.get('logging', 'csv_log_file', fallback='logs/jobbot_logs.csv'), log_level))
            except Exception as e: print(f'CSV logging error: {e}')

        logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s', handlers=handlers)
        self.logger = logging.getLogger(__name__)
        self.logger.info('Bot initialized')

    def random_wait(self, min_sec=None, max_sec=None):
        if min_sec is None:
            min_sec = float(self.config.get(
                'bot', 'random_delay_min', fallback=2))
        if max_sec is None:
            max_sec = float(self.config.get(
                'bot', 'random_delay_max', fallback=5))
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)

    def setup_driver(self):
        try:
            options = webdriver.ChromeOptions()
            for arg in ['--disable-blink-features=AutomationControlled', '--start-maximized', '--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', 'user-agent=Mozilla/5.0']:
                options.add_argument(arg)
            if self.config.getboolean('bot', 'headless', fallback=False): options.add_argument('--headless')

            self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            self.driver.implicitly_wait(int(self.config.get('bot', 'implicit_wait', fallback=10)))
            self.wait = WebDriverWait(self.driver, int(self.config.get('bot', 'explicit_wait', fallback=30)))
            return True
        except Exception as e:
            self.logger.error(f'Driver setup failed: {e}')
            return False

    def _find_element(self, selectors, wait_time=5):
        for by_method, selector in selectors:
            try:
                return WebDriverWait(self.driver, wait_time).until(EC.presence_of_element_located((by_method, selector)))
            except: continue
        return None

    def load_candidates(self):
        try:
            candidates_file = self.base_dir / 'data' / 'candidates.csv'
            if not candidates_file.exists(): return []
            df = pd.read_csv(candidates_file)
            return df[df['Status'].str.lower() == 'active'].to_dict('records')
        except Exception as e:
            self.logger.error(f'Error loading candidates: {e}')
            return []

    def login(self, email, password):
        try:
            self.driver.get('https://jobs.insightglobal.com/')
            self.random_wait()

            # Click Sign In
            sign_in = self.wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH,
                     "//a[@href='https://jobs.insightglobal.com/users/login.aspx']")
                )
            )
            sign_in.click()
            self.random_wait()

            # Enter credentials
            email_field = self.wait.until(
                EC.presence_of_element_located((By.ID, 'txtUser')))
            password_field = self.wait.until(
                EC.presence_of_element_located((By.ID, 'txtPassword')))

            email_field.clear()
            email_field.send_keys(email)
            self.random_wait(0.5, 1.5)

            password_field.clear()
            password_field.send_keys(password)
            self.random_wait(0.5, 1.5)

            # Click login button
            login_btn = self.wait.until(
                EC.element_to_be_clickable(
                    (By.ID, 'ContentPlaceHolder1_LoginControl1_cmdOK')
                )
            )

            # Scroll the login button into view (centered)
            self.driver.execute_script(
                'arguments[0].scrollIntoView({block: "center", inline: "center"});',
                login_btn
            )
            self.random_wait(0.5, 1)  # Wait for scroll to complete

            # Click using JavaScript to ensure it works even if partially obscured
            self.driver.execute_script('arguments[0].click();', login_btn)
            self.logger.info('Clicked login button using JavaScript')
            self.random_wait()

            # Verify login success
            try:
                self.wait.until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//a[contains(@href,'logout') or contains(text(),'Sign Out')]"))
                )
                self.logger.info(f'Login successful for {email}')
                return True
            except TimeoutException:
                self.logger.error(f'Login verification failed for {email}')
                return False

        except Exception as e:
            self.logger.error(f'Login failed for {email}: {e}')
            return False

    def search_jobs(self, keywords, location):
        try:
            self.driver.get('https://jobs.insightglobal.com/')
            self.random_wait()

            self.wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="textinput"]'))).send_keys(keywords)
            loc_field = self.wait.until(EC.presence_of_element_located((By.ID, 'locationinput')))
            self.driver.execute_script("arguments[0].value = '';", loc_field)
            loc_field.send_keys(location)
            self.random_wait()

            self.wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="homesearch"]'))).click()
            self.random_wait()
            return True
        except Exception as e:
            self.logger.error(f'Search failed: {e}')
            return False

    def get_applied_jobs(self, candidate_email):
        try:
            applied_file = self.base_dir / 'data' / 'applied_jobs.csv'

            if not applied_file.exists():
                # Create new file with headers
                df = pd.DataFrame(
                    columns=['CandidateEmail', 'JobTitle', 'JobID', 'AppliedDate', 'Status'])
                df.to_csv(applied_file, index=False)
                return set()

            df = pd.read_csv(applied_file)
            candidate_jobs = df[df['CandidateEmail'] == candidate_email]
            return set(candidate_jobs['JobID'].astype(str))

        except pd.errors.EmptyDataError:
            # Handle empty or corrupted CSV file
            self.logger.warning(
                'Applied jobs CSV file is empty or corrupted, recreating...')
            df = pd.DataFrame(
                columns=['CandidateEmail', 'JobTitle', 'JobID', 'AppliedDate', 'Status'])
            df.to_csv(applied_file, index=False)
            return set()
        except Exception as e:
            self.logger.error(f'Error loading applied jobs: {e}')
            return set()

    def save_applied_job(self, candidate_email, job_title, job_id, status='Applied'):
        try:
            applied_file = self.base_dir / 'data' / 'applied_jobs.csv'

            new_record = {
                'CandidateEmail': candidate_email,
                'JobTitle': job_title,
                'JobID': job_id,
                'AppliedDate': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Status': status
            }

            if applied_file.exists():
                try:
                    df = pd.read_csv(applied_file)
                    df = pd.concat(
                        [df, pd.DataFrame([new_record])], ignore_index=True)
                except pd.errors.EmptyDataError:
                    # File exists but is empty/corrupted, create new dataframe
                    df = pd.DataFrame([new_record])
            else:
                df = pd.DataFrame([new_record])

            df.to_csv(applied_file, index=False)
            self.logger.info(f'Saved application record: {job_title}', extra={
                             'candidate_email': candidate_email})

        except Exception as e:
            self.logger.error(f'Error saving applied job: {e}', extra={
                              'candidate_email': candidate_email})

    def apply_to_jobs(self, candidate, max_applications=10):
        try:
            applied_jobs = self.get_applied_jobs(candidate['Email'])
            count = 0
            job_index = 0

            while count < max_applications:
                try:
                    jobs = self.driver.find_elements(By.XPATH, '//div[@class="job-title"]')
                    if job_index >= len(jobs): break
                    job = jobs[job_index]
                except: break

                try:
                    self.driver.execute_script('window.scrollTo(0, 0);')
                    self.driver.execute_script('arguments[0].scrollIntoView({block: "center"});', job)
                    self.random_wait(1, 2)

                    job_title = job.text.strip().split('\n')[0]
                    job_href = job.find_element(By.XPATH, ".//a").get_attribute('href')
                    job_id = None
                    if job_href:
                        if 'jobid=' in job_href: job_id = job_href.split('jobid=')[1].split('&')[0]
                        elif '/job/' in job_href: job_id = job_href.split('/job/')[1].split('/')[0].split('?')[0]
                    
                    if not job_id: job_id = job.get_attribute('data-job-id') or job.get_attribute('id') or f'job_{job_index}'

                    if job_id in applied_jobs:
                        job_index += 1
                        continue

                    self.driver.execute_script('arguments[0].click();', job)
                    self.random_wait()

                    apply_btn = self._find_element([
                        (By.XPATH, '//a[contains(@class, "quick-apply")]'),
                        (By.XPATH, '//a[contains(text(), "Apply")]'),
                        (By.XPATH, '//button[contains(text(), "Apply")]'),
                        (By.XPATH, '//input[@value="Apply"]')
                    ])

                    if not apply_btn:
                        self.save_applied_job(candidate['Email'], job_title, job_id, 'No Apply Button')
                        self.driver.back()
                    else:
                        self.driver.execute_script('arguments[0].click();', apply_btn)
                        self.random_wait()
                        if self.fill_application_form(candidate):
                            self.save_applied_job(candidate['Email'], job_title, job_id, 'Applied')
                            count += 1
                        else:
                            self.save_applied_job(candidate['Email'], job_title, job_id, 'Form Error')
                    
                    self.random_wait()
                except Exception as e:
                    self.logger.error(f'Error applying to job: {e}')
                job_index += 1

            self.logger.info(f'Applied to {count} jobs for {candidate["Email"]}')
            return count
        except Exception as e:
            self.logger.error(f'Apply process error: {e}')
            return 0

    def fill_application_form(self, candidate):
        try:
            resume_radio = self._find_element([
                (By.ID, 'ContentPlaceHolder1_grdItem_btnSelect_0'),
                (By.ID, 'grdItem_btnSelect_0'),
                (By.XPATH, "//input[@type='radio' and contains(@id, 'btnSelect')]")
            ])
            if resume_radio: self.driver.execute_script('arguments[0].click();', resume_radio)

            for field_type, selectors, value in [
                ('LinkedIn', [(By.ID, 'ContentPlaceHolder1_txtLinkedInUrl'), (By.ID, 'txtLinkedInUrl')], candidate.get('LinkedInUrl', '')),
                ('Phone', [(By.ID, 'ContentPlaceHolder1_txtPhone2'), (By.ID, 'txtPhone2')], candidate['Phone'])
            ]:
                field = self._find_element(selectors)
                if field:
                    self.driver.execute_script("arguments[0].removeAttribute('readonly');", field)
                    field.clear()
                    field.send_keys(value)

            min_req = self._find_element([(By.ID, 'ContentPlaceHolder1_chkMinReq_0'), (By.ID, 'chkMinReq_0'), (By.XPATH, "//input[@value='Yes']")])
            if min_req: self.driver.execute_script('arguments[0].click();', min_req)

            apply_now = self._find_element([(By.ID, 'ContentPlaceHolder1_cmdApply'), (By.ID, 'cmdApply'), (By.XPATH, "//input[@value='Apply Now']")])
            if apply_now:
                self.driver.execute_script('arguments[0].click();', apply_now)
                self.random_wait(2, 3)
            else: return False

            back_btn = self._find_element([(By.XPATH, "//a[contains(text(), 'Back to Search')]")], 10)
            if back_btn: self.driver.execute_script('arguments[0].click();', back_btn)
            else: self.driver.back()
            
            return True
        except Exception as e:
            self.logger.error(f'Form fill error: {e}')
            return False

    def logout(self):
        try:
            # Try multiple logout selectors
            logout_selectors = [
                "//a[@href='/?logout=1']",
                "//a[contains(@href,'logout')]",
                "//a[contains(text(),'Logout')]",
                "//a[contains(text(),'Sign Out')]"
            ]

            logout_link = None
            for selector in logout_selectors:
                try:
                    logout_link = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    if logout_link:
                        self.logger.info(f'Found logout link with: {selector}')
                        break
                except TimeoutException:
                    continue

            if not logout_link:
                self.logger.warning('Logout link not found, continuing anyway')
                return True

            # Click logout using JavaScript
            self.driver.execute_script('arguments[0].click();', logout_link)
            self.random_wait()
            self.logger.info('Logged out successfully')
            return True
        except Exception as e:
            self.logger.error(f'Logout failed: {e}')
            # Even if logout fails, we can continue to next candidate
            return True

    def process_candidate(self, candidate):
        try:
            self.logger.info(f'Processing candidate: {candidate["Email"]}')
            self.current_candidate = candidate

            # Login
            if not self.login(candidate['Email'], candidate['Password']):
                self.logger.error(f'Login failed for {candidate["Email"]}')
                return False

                # Get search keywords
            keywords_list = self.config.get('search', 'keywords').split(',')

            # Check if candidate has a preferred location, otherwise use config
            if 'PreferredLocation' in candidate and candidate['PreferredLocation'] and str(candidate['PreferredLocation']).strip():
                locations_list = [str(candidate['PreferredLocation']).strip()]
                self.logger.info(
                    f'Using candidate preferred location: {locations_list[0]}')
            else:
                locations_list = self.config.get(
                    'search', 'location').split(',')
                self.logger.info(f'Using config locations: {locations_list}')

            max_apps = int(self.config.get(
                'search', 'max_applications_per_candidate', fallback=10))

            total_applications = 0

            # Search and apply for each keyword-location combination
            for keyword in keywords_list:
                keyword = keyword.strip()
                for location in locations_list:
                    location = location.strip()

                    if total_applications >= max_apps:
                        break

                    self.logger.info(f'Searching: {keyword} in {location}')

                    if self.search_jobs(keyword, location):
                        apps = self.apply_to_jobs(
                            candidate, max_apps - total_applications)
                        total_applications += apps

                    if total_applications >= max_apps:
                        break

            self.logger.info(
                f'Total applications for {candidate["Email"]}: {total_applications}')

            # Log activity to API if there were applications
            if total_applications > 0:
                try:
                    candidate_id = int(candidate.get('CandidateID', 0))
                    if candidate_id > 0:
                        notes = f"Applied to {total_applications} jobs. Log: {self.log_file.name}"
                        success = self.activity_logger.log_activity(
                            activity_count=total_applications,
                            notes=notes,
                            candidate_id=candidate_id
                        )
                        if success:
                            self.logger.info(f'Logged {total_applications} applications to API for candidate {candidate_id}')
                        else:
                            self.logger.error(f'Failed to log {total_applications} applications to API for candidate {candidate_id}')
                    else:
                        self.logger.warning(f'No CandidateID found for {candidate["Email"]}, skipping API logging')
                except Exception as e:
                    self.logger.error(f'Failed to log activity to API: {e}')
            else:
                self.logger.info(f'No jobs applied to for {candidate["Email"]}, skipping API logging')

            # Logout
            self.logout()

            return True

        except Exception as e:
            self.logger.error(
                f'Error processing candidate {candidate["Email"]}: {e}')
            return False

    def run(self):
        try:
            # Setup driver
            if not self.setup_driver():
                self.logger.error('Failed to setup driver. Exiting.')
                return

            # Load candidates
            candidates = self.load_candidates()

            if not candidates:
                self.logger.error('No active candidates found. Exiting.')
                return

            # Process each candidate
            for idx, candidate in enumerate(candidates, 1):
                self.logger.info(f'\n{'='*50}')
                self.logger.info(
                    f'Processing candidate {idx}/{len(candidates)}')
                self.logger.info(f'{'='*50}\n')

                self.process_candidate(candidate)

                # Add delay between candidates
                if idx < len(candidates):
                    delay = random.uniform(30, 60)
                    self.logger.info(
                        f'Waiting {delay:.1f} seconds before next candidate...')
                    time.sleep(delay)

            self.logger.info('\nAll candidates processed successfully!')

        except KeyboardInterrupt:
            self.logger.warning('Process interrupted by user')
        except Exception as e:
            self.logger.error(f'Unexpected error in run: {e}')
        finally:
            if self.driver:
                self.driver.quit()
                self.logger.info('Browser closed')


def main():
    print('='*60)
    print('Insight Global Job Application Bot')
    print('Multi-Candidate Automation')
    print('='*60)
    print()

    bot = InsightGlobalJobBot()
    bot.run()


if __name__ == '__main__':
    main()
