# METU Linguistics Society - Sponsorship Mail Bot V1
A CLI-driven, fault-tolerant mail merge engine designed specifically for the METU Linguistics Society. It allows board members to dispatch customized, attachment-ready sponsorship emails through the official university SMTP server without triggering spam filters.

## Features
* **Template Injection:** Maps CSV columns directly to template variables.
* **Fault Tolerance:** Saves state automatically. If the network drops, it remembers exactly where it left off.
* **Anti-Spam Evasion:** Introduces randomized jitter (8-15 seconds) between emails to prevent IP blacklisting.
* **Decentralized Workload:** Allows board members to process specific row chunks (e.g., rows 50-100) using their own signature.

### 1. Prerequisites
You need Python 3.10+ installed on your system.
Install the required environment variable manager:
```python
pip install python-dotenv
```
### 2. Setup & Authentication
1. Clone or download this repository.
2. Locate the `.env.example` file.
3. Duplicate it and rename the copy to strictly `.env`.
4. Open `.env` and insert the official `dilbilim@metu.edu.tr` password.
*Note: The `.env` file is in the `.gitignore` by default. Never share the production password in plaintext over unsecured channels.*

### 3. Data Preparation
The script requires three assets in the same directory to run successfully:

**A. The Data (`sponsors.csv`)**
Your data must be exported as a standard CSV (Comma Separated Values) file. The first row must be headers.
Required Headers:
* `company_mail`: The exact target email address.
* Any other header you use in your template (e.g., `first_name`, `company_name`, `target_event`).

**B. The Template (`template.txt`)**
A plain text file containing your email body. Use `{curly_braces}` to match the column headers in your CSV.
Example:
* Dear {first_name},
* We believe {company_name} would be an excellent fit for {target_event}...

C. The Attachment (`prospectus.pdf`)
The file you are sending. This is loaded into memory once to optimize disk usage.

### 4. Execution
Run the script from your terminal. You must define your row assignment and your signature context.
Basic Usage:
```python
python mailer.py --start 2 --end 50 --name "Your Name" --title "Your Board Title"
```
Advanced Usage (Custom Files):
If your files have different names, pass them as arguments:
```python
python mailer.py --start 51 --end 100 --name "Ahmet" --title "President" --data "tech_sponsors.csv" --template "tech_template.txt" --attachment "tech_packet.pdf"
```

**CLI Arguments Reference**
|Argument|Type|Requirement|Description|
|--start|Integer|Required|Excel row number to begin sending from.|
|--end|Integer|Required|Excel row number to stop at.|
|--name|String|Required|Your full name for the signature.|
|--title|String|Required|Your society title (e.g., "Treasurer").|
|--phone|String|Optional|Your phone number for the signature.|
|--data|String|Optional|Path to CSV (Defaults to sponsors.csv).|
|--template|String|Optional|Path to template (Defaults to template.txt).|
|--attachment|String|Optional|Path to attachment (Defaults to prospectus.pdf).|

### 5. Fault Tolerance & Resuming
If your internet disconnects or the script crashes mid-batch, do not change your `--start` argument.
The bot creates a hidden `batch_state.json` file to track the last successful email. Simply re-run your exact command. The bot will automatically skip the rows that were already sent and resume from the point of failure.
When the entire batch is 100% complete, the state file will clear itself automatically.
