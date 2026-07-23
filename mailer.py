import os
import json
import csv
import argparse
import smtplib
import ssl
import time
import random
import mimetypes
from email.message import EmailMessage
from dotenv import load_dotenv

# Load secrets from the .env file (e.g., SMTP_PASSWORD, SMTP_USER)
# Your .env file should look like this:
# SMTP_USER="dilbilim@metu.edu.tr"
# SMTP_PASSWORD="your_actual_password_here"
load_dotenv()

class CheckpointManager:
    """Handles saving and loading the execution state to prevent duplicate emails."""
    
    def __init__(self, cursor_file: str = "batch_state.json"):
        self.cursor_file = cursor_file

    def get_last_processed_row(self) -> int:
        """Reads the cursor file to find where the script last succeeded."""
        if not os.path.exists(self.cursor_file):
            return 0  # Start from the beginning if no checkpoint exists
        
        try:
            with open(self.cursor_file, 'r', encoding='utf-8') as file:
                data = json.load(file)
                return data.get("last_row", 0)
        except (json.JSONDecodeError, IOError):
            return 0

    def save_checkpoint(self, row_index: int) -> None:
        """Records the last successful row index to disk safely."""
        data = {"last_row": row_index}
        temp_file = f"{self.cursor_file}.tmp"
        
        # Write to a temp file first, then replace to prevent corruption mid-write
        with open(temp_file, 'w', encoding='utf-8') as file:
            json.dump(data, file)
            
        os.replace(temp_file, self.cursor_file)

    def clear_checkpoint(self) -> None:
        """Deletes the cursor file when a batch is completely finished."""
        if os.path.exists(self.cursor_file):
            os.remove(self.cursor_file)

def setup_cli() -> argparse.Namespace:
    """Configures the CLI for runtime variables (row ranges and sender info)."""
    parser = argparse.ArgumentParser(description="METU Linguistics Society Mail Bot")
    
    # Pagination arguments
    parser.add_argument("--start", type=int, required=True, help="Row index to start sending from (e.g., 2)")
    parser.add_argument("--end", type=int, required=True, help="Row index to stop sending at (e.g., 50)")
    
    # Sender Context arguments
    parser.add_argument("--name", type=str, required=True, help="Your full name (e.g., 'Ahmet')")
    parser.add_argument("--title", type=str, required=True, help="Your board title (e.g., 'President')")
    parser.add_argument("--phone", type=str, default="", help="Optional: Your phone number")
    
    # File paths
    parser.add_argument("--data", type=str, default="sponsors.csv", help="Path to your CSV file")
    parser.add_argument("--template", type=str, default="template.txt", help="Path to your email template file")
    parser.add_argument("--attachment", type=str, default="prospectus.pdf", help="Path to the attachment")

    return parser.parse_args()

def load_template(template_path: str) -> str:
    """Reads the raw text/HTML template into memory."""
    with open(template_path, 'r', encoding='utf-8') as file:
        return file.read()

def get_target_rows(csv_path: str, start_index: int, end_index: int) -> list[dict]:
    """Reads the CSV and extracts ONLY the rows assigned to this specific execution."""
    target_rows = []
    with open(csv_path, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        
        # Start at 2 to map exactly to Excel's visual row numbers (assuming row 1 is headers)
        for current_row_num, row_data in enumerate(reader, start=2):
            if start_index <= current_row_num <= end_index:
                row_data['_row_num'] = current_row_num
                target_rows.append(row_data)
                
    return target_rows

def get_attachment_data(filepath: str) -> tuple[bytes, str, str, str]:
    """Loads the attachment into memory once to prevent disk I/O bottlenecks."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Attachment not found: {filepath}")
    
    ctype, encoding = mimetypes.guess_type(filepath)
    if ctype is None or encoding is not None:
        ctype = 'application/octet-stream'
    maintype, subtype = ctype.split('/', 1)
    
    with open(filepath, 'rb') as f:
        data = f.read()
        
    filename = os.path.basename(filepath)
    return data, maintype, subtype, filename

def main():
    args = setup_cli()
    
    # METU SMTP Configuration
    SMTP_SERVER = "smtp.metu.edu.tr" 
    SMTP_PORT = 587
    SMTP_USER = os.getenv("SMTP_USER", "dilbilim@metu.edu.tr")
    SMTP_PASS = os.getenv("SMTP_PASSWORD")
    
    if not SMTP_PASS:
        print("CRITICAL: SMTP_PASSWORD not found in .env file. Exiting.")
        return

    print("Initializing METU Linguistics Mail Bot...")
    
    # Load State & Assets
    target_rows = get_target_rows(args.data, args.start, args.end)
    template_text = load_template(args.template)
    checkpoint_manager = CheckpointManager()
    last_processed = checkpoint_manager.get_last_processed_row()
    
    try:
        att_data, maintype, subtype, att_name = get_attachment_data(args.attachment)
    except Exception as e:
        print(f"CRITICAL: {e}\nCheck your attachment file path.")
        return

    context = ssl.create_default_context()
    
    try:
        print(f"Connecting to {SMTP_SERVER}...")
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=context) # Encrypt connection
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            print("Authentication successful. Beginning batch dispatch.\n" + "-"*40)

            row_num = 0 # Fallback definition in case target_rows is empty
            for row in target_rows:
                row_num = row['_row_num']
                
                if row_num <= last_processed:
                    print(f"[{row_num}] Skipped (Already processed in previous run)")
                    continue
                
                # Merge CSV data with CLI arguments
                template_context = {**row} 
                template_context.update({
                    'sender_name': args.name,
                    'sender_title': args.title,
                    'sender_phone': args.phone
                })
                
                try:
                    body = template_text.format(**template_context)
                except KeyError as e:
                    print(f"[{row_num}] FAILED: Template contains {e}, but it is missing from the CSV columns.")
                    continue
                    
                # Construct the payload
                msg = EmailMessage()
                msg.set_content(body)
                msg['Subject'] = f"Partnership Opportunity: METU Linguistics Society" 
                msg['From'] = SMTP_USER
                msg['To'] = row.get('company_mail') 
                
                msg.add_attachment(att_data, maintype=maintype, subtype=subtype, filename=att_name)
                
                # Dispatch and Save State
                server.send_message(msg)
                checkpoint_manager.save_checkpoint(row_num)
                
                print(f"[{row_num}/{args.end}] SUCCESS -> Sent to {row.get('company_mail')}")
                
                # Evasion Tactics (Jitter)
                if row_num < args.end:
                    delay = random.uniform(8.0, 15.0)
                    time.sleep(delay)
                    
        print("-" * 40 + "\nBatch completed successfully.")
        
    except smtplib.SMTPAuthenticationError:
        print("CRITICAL: Invalid username or password. Check your .env file.")
    except Exception as e:
        print(f"\nNETWORK/EXECUTION ERROR at Row {row_num}: {e}")
        print("Connection dropped. The checkpoint is saved. Rerun the script to resume.")

if __name__ == "__main__":
    main()
