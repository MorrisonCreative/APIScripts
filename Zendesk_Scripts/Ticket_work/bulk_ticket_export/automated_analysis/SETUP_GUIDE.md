# Automated Ticket Analysis Setup Guide

This guide will help you set up the automated Zendesk ticket analysis system that runs every Monday at 5 AM Pacific time.

**🔄 Dual Credential Support:** The system automatically exports tickets from TWO Zendesk instances (credential sets) and combines them for a unified analysis.

**✨ This system is fully portable** - all scripts auto-detect their location and can be copied to any machine or directory!

## 📋 What Was Created

The following files have been created in this directory:

```
/Users/hunter-morrison/git/APIScripts/Zendesk_Scripts/Ticket_work/bulk_ticket_export/automated_analysis/
├── ticket_analyzer.py        ← Main orchestrator: runs export, merges data, calls Gemini, sends email
├── zendesk_exporter.py       ← Zendesk API client: fetches & filters tickets, outputs JSON
├── run_analysis.sh            ← Quick test script (dry-run mode, no email sent)
├── cron_wrapper.sh            ← Cron job wrapper (loads env vars, calls ticket_analyzer.py)
├── requirements.txt           ← Python dependencies
├── logs/                      ← Log directory for cron output
└── SETUP_GUIDE.md            ← This file
```

### How the scripts work together

`ticket_analyzer.py` is the entry point for every run. It calls `zendesk_exporter.py` as a subprocess — twice, once per credential set — passing the date range and priority filter as CLI arguments. The exporter hits the Zendesk REST API, pulls full ticket history, and writes the results to `exported_tickets_set1.json` and `exported_tickets_set2.json`. The analyzer then merges both files, chunks the tickets, sends them to Gemini for analysis, and emails the final report.

**You should never need to run `zendesk_exporter.py` directly** — `ticket_analyzer.py` (or `cron_wrapper.sh`) handles that automatically.

## 🔧 Setup Steps

### Step 1: Configure API Keys

You need to set up environment variables for the APIs. Add these to your `~/.zshrc` file:

```bash
# Edit your shell config
nano ~/.zshrc

# Add these lines (fill in your actual values):

# --- Zendesk API - Credential Set 1 ---
export ZENDESK_SUBDOMAIN="your_subdomain"
export ZENDESK_EMAIL="your_zendesk_email@company.com"
export ZENDESK_API_TOKEN="your_zendesk_api_token"

# --- Zendesk API - Credential Set 2 ---
export ZENDESK_SUBDOMAIN_2="your_second_subdomain"
export ZENDESK_EMAIL_2="your_second_zendesk_email@company.com"
export ZENDESK_API_TOKEN_2="your_second_zendesk_api_token"

# --- Priority Field IDs (Custom field ID for ticket priority) ---
# Set 1: Use either PRIORITY_FIELD_ID or PRIORITY_FIELD_ID_1
export PRIORITY_FIELD_ID="360047533253"
# Set 2: Must use PRIORITY_FIELD_ID_2
export PRIORITY_FIELD_ID_2="123456789012"

# --- Gemini API Key ---
export GOOGLE_API_KEY="AIza..."

# --- Gmail SMTP Configuration ---
export EMAIL_FROM="your_email@gmail.com"
export EMAIL_PASSWORD="your_16_char_app_password"
export EMAIL_TO="recipient1@email.com,recipient2@email.com"
```

**Important:** Save the file and reload it:
```bash
source ~/.zshrc
```

#### Finding Your Priority Field ID

Each Zendesk instance may have a different custom field ID for ticket priority. To find yours:

1. Go to your Zendesk Admin Center
2. Navigate to **Objects and rules** → **Tickets** → **Fields**
3. Click on your "Ticket Priority" field (or equivalent custom field)
4. Look at the URL - it will contain the field ID
   - Example: `https://yourcompany.zendesk.com/admin/objects-rules/tickets/ticket-fields/360047533253`
   - The ID is: `360047533253`
5. Set this as `PRIORITY_FIELD_ID` (or `PRIORITY_FIELD_ID_1`) for credential set 1
6. Repeat for your second Zendesk instance and set as `PRIORITY_FIELD_ID_2`

**Note:** The system will automatically export tickets from BOTH credential sets and combine them for analysis.

### Step 2: Set Up Gmail App Password

Since you're using Gmail, you need an App Password (not your regular Gmail password):

1. Go to your Google Account: https://myaccount.google.com/
2. Navigate to: **Security** → **2-Step Verification** (enable if not already)
3. Scroll down to: **App passwords**
4. Select app: **Mail**
5. Generate password (will be 16 characters like: `abcd efgh ijkl mnop`)
6. Copy this password and use it for `EMAIL_PASSWORD` environment variable

### Step 3: Test the System

Before setting up the cron job, test that everything works:

#### Test 1: Dry Run with P1 Tickets
```bash
cd /Users/hunter-morrison/git/APIScripts/Zendesk_Scripts/Ticket_work/bulk_ticket_export
./run_analysis.sh P1
```

This will:
- Export P1 tickets from the last 7 days (from BOTH credential sets)
- Combine the tickets
- Analyze them with Gemini AI
- Print the analysis (without sending email)

#### Test 2: Dry Run with All Tickets
```bash
./run_analysis.sh
```

#### Test 3: Send Real Email (P1 Tickets)
```bash
python3 ticket_analyzer.py --priorities P1
```

This will actually send the email to your configured recipients.

### Step 4: Install Cron Job

Install the cron job to run every Monday at 5 AM Pacific:

```bash
# First, get the full path to the wrapper script
cd /path/to/your/bulk_ticket_export  # Navigate to your script directory
WRAPPER_PATH="$(pwd)/cron_wrapper.sh"
LOG_PATH="$(pwd)/logs/cron.log"

# Open crontab editor
crontab -e

# Add this line at the bottom (replace paths with yours from above):
0 5 * * 1 /full/path/to/cron_wrapper.sh >> /full/path/to/logs/cron.log 2>&1

# Example for current installation:
# 0 5 * * 1 /Users/hunter-morrison/git/APIScripts/Zendesk_Scripts/Ticket_work/bulk_ticket_export/cron_wrapper.sh >> /Users/hunter-morrison/git/APIScripts/Zendesk_Scripts/Ticket_work/bulk_ticket_export/logs/cron.log 2>&1

# Save and exit (in vi/vim: press ESC, type :wq, press ENTER)
```

**Cron Syntax Breakdown:**
- `0` = minute (0)
- `5` = hour (5 AM)
- `*` = day of month (any)
- `*` = month (any)
- `1` = day of week (Monday, where 0=Sunday, 1=Monday)

### Step 5: Verify Cron Installation

Check that your cron job was installed correctly:

```bash
crontab -l
```

You should see the line you just added.

### Step 6: Test Cron Wrapper Manually

Before waiting for Monday at 5 AM, test the cron wrapper:

```bash
./cron_wrapper.sh
```

This will:
- Load your environment variables
- Run the analysis with Gemini AI
- Send the actual email
- Log output to `logs/cron.log`

Check the log:
```bash
cat logs/cron.log
```

#### Testing with a Custom Date Range

To test the cron wrapper against a specific time window without modifying any code, pass `--start-date` and `--end-date`:

```bash
./cron_wrapper.sh --start-date 2026-05-01 --end-date 2026-05-15
```

Both flags are optional — omitting them falls back to the default (last 7 days for recent tickets, last 6 months for the open P1 lookback). You can also pass just one:

```bash
./cron_wrapper.sh --start-date 2026-01-01   # custom start, end defaults to today
./cron_wrapper.sh --end-date 2026-04-30     # custom end, start defaults to 7 days before end
```

The date range is passed through to both the exporter and the analyzer automatically.

## 🎯 Usage

### Manual Runs

**Run analysis without sending email (dry-run):**
```bash
./run_analysis.sh P1        # Test with P1 tickets only
./run_analysis.sh P1,P2     # Test with P1 and P2 tickets
./run_analysis.sh           # Test with all tickets
```

**Send actual email:**
```bash
python3 ticket_analyzer.py --priorities P1      # P1 tickets only
python3 ticket_analyzer.py --priorities P1,P2   # P1 and P2 tickets
python3 ticket_analyzer.py                       # All tickets
```

### Automated Runs

The cron job will automatically run every **Monday at 5:00 AM Pacific Time**.

- Exports tickets from the last 7 days from **BOTH Zendesk instances** (credential sets 1 & 2)
- Combines tickets into a single dataset
- Analyzes with Gemini AI
- Filters for P1 tickets by default
- Sends email to configured recipients
- Logs output to `logs/cron.log`

### Filtering by Custom Field Value (Wildcard)

You can filter exported tickets by any Zendesk custom field. Filtering is client-side (applied after the API fetch) and supports wildcards, AND logic, OR logic, or any combination.

#### AND filters — all must match (`--field-filter`)

```bash
# Keep only tickets where field 360047533253 starts with "v28"
python3 zendesk_exporter.py --start-date 2024-01-01 --end-date 2024-01-31 \
    --field-filter 360047533253=v28*

# Both filters must match
python3 zendesk_exporter.py --start-date 2024-01-01 --end-date 2024-01-31 \
    --field-filter 360047533253=v28* \
    --field-filter 123456789=prod*
```

#### OR within a single field — comma-separated patterns

```bash
# Field 360047533253 matches "v28..." OR "v29..."
python3 zendesk_exporter.py --start-date 2024-01-01 --end-date 2024-01-31 \
    --field-filter 360047533253=v28*,v29*
```

#### OR between different fields (`--or-field-filter`)

```bash
# Field 360047533253 starts with "v28" OR field 123456 equals "false"
python3 zendesk_exporter.py --start-date 2024-01-01 --end-date 2024-01-31 \
    --or-field-filter 360047533253=v28* \
    --or-field-filter 123456=false
```

#### Combined AND + OR

AND filters and the OR group are evaluated together — both conditions must be satisfied:

```bash
# Field 999 must equal "active" (AND), AND either field 360047533253=v28* or field 123456=false (OR group)
python3 zendesk_exporter.py --start-date 2024-01-01 --end-date 2024-01-31 \
    --field-filter 999=active \
    --or-field-filter 360047533253=v28* \
    --or-field-filter 123456=false
```

**Wildcard syntax (shell-style):**

| Pattern | Matches |
|---------|---------|
| `v28*`  | Any value starting with "v28" |
| `*prod*` | Any value containing "prod" |
| `v?.0`  | "v1.0", "v2.0", etc. |
| `[ab]*` | Any value starting with "a" or "b" |

Matching is **case-insensitive**. A ticket missing a filtered field is treated as an empty string.

Applied filters are recorded in the JSON output under `export_metadata.field_filters` (AND) and `export_metadata.or_field_filters` (OR).

### Changing Priority Filter

To change which priorities are analyzed, edit `cron_wrapper.sh`:

```bash
# Line 28 - change from:
python3 ticket_analyzer.py --priorities P1

# To analyze P1 and P2:
python3 ticket_analyzer.py --priorities P1,P2

# To analyze all tickets (remove --priorities):
python3 ticket_analyzer.py
```

## 📧 Email Content

Each email will include:

1. **Total ticket count** for the 7-day period
2. **Per-ticket analysis:**
   - Ticket ID and subject
   - Status and priority
   - Response time (time to first response)
   - Time to resolution (if closed)
   - Brief 1-2 sentence summary
3. **Themes and patterns:**
   - Common issue types
   - Customer segments affected
   - Notable trends or concerns

## 🔍 Monitoring

### Check Cron Execution Logs

```bash
# View full log
cat logs/cron.log

# View last 50 lines
tail -n 50 logs/cron.log

# Watch logs in real-time (if running manually)
tail -f logs/cron.log
```

### Verify Timezone

Check your system timezone:
```bash
date
```

If not Pacific time, the cron wrapper explicitly sets `TZ=America/Los_Angeles`.

## 🛠️ Troubleshooting

### Issue: "No module named 'google.genai'"

**Solution:** Reinstall dependencies:
```bash
pip3 install -r requirements.txt
```

### Issue: "GOOGLE_API_KEY environment variable not set"

**Solution:** Make sure you added the key to `~/.zshrc` and ran `source ~/.zshrc`

To test:
```bash
echo $GOOGLE_API_KEY
```

### Issue: Email not sending

**Possible causes:**
1. Gmail App Password not set up correctly
2. 2-Factor Authentication not enabled on Gmail
3. Wrong `EMAIL_FROM` or `EMAIL_PASSWORD`

**Solution:** Double-check Gmail App Password setup (Step 2 above)

### Issue: Cron job not running

**Check if cron is running:**
```bash
# Test the wrapper manually
./cron_wrapper.sh

# Check logs
cat logs/cron.log
```

**Common issue:** Environment variables not loading in cron
- Cron runs in a minimal environment
- The `cron_wrapper.sh` sources `~/.zshrc` to load variables
- Make sure all env vars are in `~/.zshrc`

### Issue: Wrong timezone

If your system isn't set to Pacific time:

1. The `cron_wrapper.sh` sets `TZ=America/Los_Angeles`
2. Verify with: `date` (should show PST/PDT)
3. Cron uses system time, so 5 AM cron = 5 AM system time

### Issue: Priority filter not working

**Symptoms:** All tickets are showing as "unassigned" priority or priority filter has no effect

**Solution:** Check your priority field IDs:
1. Verify the field ID in each Zendesk instance (see "Finding Your Priority Field ID" above)
2. Make sure you've set the correct environment variables:
   - `PRIORITY_FIELD_ID` or `PRIORITY_FIELD_ID_1` for credential set 1
   - `PRIORITY_FIELD_ID_2` for credential set 2
3. Reload your shell config: `source ~/.zshrc`
4. Test: `echo $PRIORITY_FIELD_ID` and `echo $PRIORITY_FIELD_ID_2`

## 🎛️ Customization

### Change Analysis Timeframe

**For one-off runs**, pass dates directly without editing any code:

```bash
# Via cron wrapper (recommended — runs full export + analysis):
./cron_wrapper.sh --start-date 2026-05-01 --end-date 2026-05-15

# Via ticket_analyzer.py directly (skips export, uses existing exported files):
python3 ticket_analyzer.py --start-date 2026-05-01 --end-date 2026-05-15 --dry-run
```

**To permanently change the default window**, edit `ticket_analyzer.py` line ~48:

```python
def calculate_date_range():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)  # Change 7 to any number
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
```

### Change Cron Schedule

Edit crontab (`crontab -e`):

```bash
# Every Monday at 5 AM
0 5 * * 1 /path/to/cron_wrapper.sh

# Every day at 8 AM
0 8 * * * /path/to/cron_wrapper.sh

# Every Friday at 5 PM (17:00)
0 17 * * 5 /path/to/cron_wrapper.sh

# First day of every month at 9 AM
0 9 1 * * /path/to/cron_wrapper.sh
```

### Customize Analysis Prompt

Edit `ticket_analyzer.py`, function `analyze_with_gemini()` around line ~120

Change the prompt to focus on different aspects of the tickets.

## 📞 Support

If you encounter issues:

1. Check `logs/cron.log` for error messages
2. Run `./run_analysis.sh P1` to test without sending email
3. Verify environment variables are set:
   ```bash
   env | grep -E "ZENDESK|GOOGLE|EMAIL|PRIORITY_FIELD"
   ```

## ✅ Quick Verification Checklist

- [ ] Python dependencies installed (`pip3 install -r requirements.txt`)
- [ ] Environment variables set in `~/.zshrc`:
  - [ ] ZENDESK credentials for both sets (ZENDESK_*, ZENDESK_*_2)
  - [ ] Priority field IDs for both sets (PRIORITY_FIELD_ID, PRIORITY_FIELD_ID_2)
  - [ ] GOOGLE_API_KEY for Gemini AI
  - [ ] EMAIL_* for Gmail SMTP
- [ ] Gmail App Password created and configured
- [ ] Test run successful (`./run_analysis.sh P1`)
- [ ] Real email test successful (`python3 ticket_analyzer.py --priorities P1`)
- [ ] Cron job installed (`crontab -l` shows the entry)
- [ ] Cron wrapper tested (`./cron_wrapper.sh`)

---

## 📦 Installing on a New Machine

All scripts are fully portable — they auto-detect their location at runtime, so no hardcoded paths need to change when you move them.

### Step A: Copy the scripts

**Option 1 — Clone from git (recommended):**
```bash
git clone <your-repo-url>
cd APIScripts/Zendesk_Scripts/Ticket_work/bulk_ticket_export/automated_analysis
```

**Option 2 — Transfer via archive:**
```bash
# On the source machine:
tar -czf ticket-analyzer.tar.gz /path/to/automated_analysis

# On the new machine:
tar -xzf ticket-analyzer.tar.gz
cd automated_analysis
```

### Step B: Install Python

The scripts require **Python 3.8+**.

```bash
# Check if Python is installed:
python3 --version

# macOS — install via Homebrew if missing:
brew install python3

# Ubuntu/Debian:
sudo apt-get install python3 python3-pip
```

### Step C: Install Python dependencies

```bash
pip3 install -r requirements.txt
```

This installs:
- `google-genai` — Gemini AI SDK
- `requests` — Zendesk API calls (used by `zendesk_exporter.py`)
- `markdown` — email HTML rendering

If you're using a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step D: Configure environment variables

Add all required variables to `~/.zshrc` (or `~/.bashrc` on Linux):

```bash
nano ~/.zshrc
```

```bash
# --- Zendesk API - Credential Set 1 ---
export ZENDESK_SUBDOMAIN="your_subdomain"
export ZENDESK_EMAIL="your_zendesk_email@company.com"
export ZENDESK_API_TOKEN="your_zendesk_api_token"

# --- Zendesk API - Credential Set 2 ---
export ZENDESK_SUBDOMAIN_2="your_second_subdomain"
export ZENDESK_EMAIL_2="your_second_zendesk_email@company.com"
export ZENDESK_API_TOKEN_2="your_second_zendesk_api_token"

# --- Priority Field IDs ---
export PRIORITY_FIELD_ID="360047533253"    # Credential set 1
export PRIORITY_FIELD_ID_2="123456789012"  # Credential set 2

# --- Gemini API Key ---
export GOOGLE_API_KEY="AIza..."

# --- Gmail SMTP ---
export EMAIL_FROM="your_email@gmail.com"
export EMAIL_PASSWORD="your_16_char_app_password"
export EMAIL_TO="recipient1@email.com,recipient2@email.com"
```

Reload the shell:
```bash
source ~/.zshrc
```

Verify the variables loaded:
```bash
env | grep -E "ZENDESK|GOOGLE|EMAIL|PRIORITY_FIELD"
```

### Step E: Make shell scripts executable

```bash
chmod +x run_analysis.sh cron_wrapper.sh
```

### Step F: Test the installation

```bash
# Dry run — exports tickets and prints analysis, no email sent:
./run_analysis.sh P1

# If that passes, send a real email:
python3 ticket_analyzer.py --priorities P1
```

### Step G: Install the cron job

```bash
# Get the full path to the wrapper:
WRAPPER_PATH="$(pwd)/cron_wrapper.sh"
echo $WRAPPER_PATH   # Copy this output

# Open crontab editor:
crontab -e

# Add this line (replace the path with your output from above):
0 5 * * 1 /full/path/to/cron_wrapper.sh >> /full/path/to/logs/cron.log 2>&1
```

Verify it was saved:
```bash
crontab -l
```

Test the wrapper runs end-to-end before waiting for Monday:
```bash
./cron_wrapper.sh
cat logs/cron.log
```

### What gets auto-detected vs. what you configure

| | Detail |
|---|---|
| **Auto-detected** | Script directory, paths to `zendesk_exporter.py`, output JSON files, log directory |
| **You configure** | All env vars (API keys, email credentials), cron job entry with full path |

---

**System is ready!**

Next Monday at 5 AM Pacific, you'll receive your first automated ticket analysis email.
