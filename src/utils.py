
import csv
import json
import logging
import threading
from pathlib import Path
from datetime import datetime


class CSVLogger(logging.Handler):
    """Custom logging handler that writes log records to a CSV file."""

    def __init__(self, csv_file_path, mode='a'):
        super().__init__()
        self.csv_file_path = Path(csv_file_path)
        self.mode = mode
        self._lock = threading.Lock()
        self._initialized = False

        # Ensure the directory exists
        self.csv_file_path.parent.mkdir(parents=True, exist_ok=True)

    def _initialize_csv(self):
        """Initialize CSV file with headers if it doesn't exist or is empty."""
        if not self.csv_file_path.exists() or self.csv_file_path.stat().st_size == 0:
            with open(self.csv_file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'level', 'logger', 'message', 'candidate_email'])
        self._initialized = True

    def emit(self, record):
        """Emit a log record to the CSV file."""
        if not self._initialized:
            self._initialize_csv()

        try:
            with self._lock:
                with open(self.csv_file_path, self.mode, newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)

                    # Get candidate email from logger extra data if available
                    candidate_email = getattr(record, 'candidate_email', '')

                    # Format the log record
                    timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
                    level = record.levelname
                    logger = record.name
                    message = record.getMessage()

                    writer.writerow([timestamp, level, logger, message, candidate_email])

        except Exception as e:
            # Fallback to stderr if CSV logging fails
            import sys
            print(f"CSV logging failed: {e}", file=sys.stderr)


def setup_csv_logging(csv_file_path='logs/jobbot_logs.csv', level=logging.INFO):
    """Set up CSV logging handler."""
    csv_handler = CSVLogger(csv_file_path)
    csv_handler.setLevel(level)

    # Create a formatter (though we don't use it for CSV)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    csv_handler.setFormatter(formatter)

    return csv_handler


def create_candidates_template(output_path='data/candidates_template.csv'):
    headers = ['Email', 'Password', 'FirstName', 'LastName', 'Phone', 'ResumePath', 'Status']
    sample_data = [
        ['candidate1@example.com', 'password123', 'John', 'Doe', '1234567890', 'resumes/john_doe_resume.pdf', 'Active'],
        ['candidate2@example.com', 'password456', 'Jane', 'Smith', '0987654321', 'resumes/jane_smith_resume.pdf', 'Active']
    ]
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(sample_data)
    
    print(f'Template created: {output_path}')


def generate_report(applied_jobs_csv='data/applied_jobs.csv', output_path='logs/report.json'):
    try:
        import pandas as pd
        
        df = pd.read_csv(applied_jobs_csv)
        
        report = {
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_applications': len(df),
            'by_candidate': df.groupby('CandidateEmail').size().to_dict(),
            'by_status': df.groupby('Status').size().to_dict(),
            'recent_applications': df.tail(10).to_dict('records')
        }
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f'Report generated: {output_path}')
        print(f'Total applications: {report["total_applications"]}')
        print(f'By candidate: {report["by_candidate"]}')
        
    except Exception as e:
        print(f'Error generating report: {e}')


if __name__ == '__main__':
    # Create template when run directly
    create_candidates_template()
