# Automated Ticket Analysis Setup Guide

This guide will help you set up the automated Zendesk ticket analysis system that runs every Monday at 5 AM Pacific time.

**✨ This system is fully portable** - all scripts auto-detect their location and can be copied to any machine or directory!

## 📋 What Was Created

The following files have been created in this directory:

```
/Users/hunter-morrison/git/APIScripts/Zendesk_Scripts/Ticket_work/bulk_ticket_export/
├── ticket_analyzer.py        ← Main analysis script (Claude + Gemini support)
├── run_analysis.sh            ← Quick test script (dry-run mode)
├── cron_wrapper.sh            ← Cron job wrapper
├── requirements.txt           ← Python dependencies (already installed ✓)
├── logs/                      ← Log directory for cron output
└── SETUP_GUIDE.md            ← This file
```

## 🔧 Setup Steps

### Step 1: Configure API Keys

You need to set up environment variables for the APIs. Add these to your `~/.zshrc` file:

```bash
# Edit your shell config
nano ~/.zshrc

# Add these lines (fill in your actual values):

# --- Zendesk API (already configured if zendesk_exporter.py works) ---
export ZENDESK_SUBDOMAIN="your_subdomain"
export ZENDESK_EMAIL="your_zendesk_email@company.com"
export ZENDESK_API_TOKEN="your_zendesk_api_token"

# --- LLM API Keys (choose one or both) ---
# For Claude:
export ANTHROPIC_API_KEY="sk-ant-..."

# For Gemini:
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

#### Test 1: Dry Run with Claude
```bash
cd /Users/hunter-morrison/git/APIScripts/Zendesk_Scripts/Ticket_work/bulk_ticket_export
./run_analysis.sh claude
```

This will:
- Export tickets from the last 7 days
- Analyze them with Claude
- Print the analysis (without sending email)

#### Test 2: Dry Run with Gemini
```bash
./run_analysis.sh gemini
```

#### Test 3: Send Real Email (Claude)
```bash
python3 ticket_analyzer.py --llm claude
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
- Run the analysis with Claude
- Send the actual email
- Log output to `logs/cron.log`

Check the log:
```bash
cat logs/cron.log
```

## 🎯 Usage

### Manual Runs

**Run analysis without sending email (dry-run):**
```bash
./run_analysis.sh claude    # Test with Claude
./run_analysis.sh gemini    # Test with Gemini
```

**Send actual email:**
```bash
python3 ticket_analyzer.py --llm claude   # With Claude
python3 ticket_analyzer.py --llm gemini   # With Gemini
```

### Automated Runs

The cron job will automatically run every **Monday at 5:00 AM Pacific Time**.

- Exports tickets from the last 7 days
- Analyzes with Claude (default)
- Sends email to configured recipients
- Logs output to `logs/cron.log`

### Switching Between Claude and Gemini

To change the default LLM used by cron, edit `cron_wrapper.sh`:

```bash
# Line 23 - change from:
python3 ticket_analyzer.py --llm claude

# To:
python3 ticket_analyzer.py --llm gemini
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

### Issue: "No module named 'anthropic'"

**Solution:** Reinstall dependencies:
```bash
pip3 install -r requirements.txt
```

### Issue: "ANTHROPIC_API_KEY environment variable not set"

**Solution:** Make sure you added the keys to `~/.zshrc` and ran `source ~/.zshrc`

To test:
```bash
echo $ANTHROPIC_API_KEY
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

## 🎛️ Customization

### Change Analysis Timeframe

Edit `ticket_analyzer.py`, line ~48:

```python
def calculate_date_range():
    """Calculate date range for last 7 days."""
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

Edit `ticket_analyzer.py`, lines ~113-135 (Claude) or ~158-180 (Gemini)

Change the prompt to focus on different aspects of the tickets.

## 📞 Support

If you encounter issues:

1. Check `logs/cron.log` for error messages
2. Run `./run_analysis.sh claude --dry-run` to test without sending email
3. Verify environment variables are set: `env | grep -E "ZENDESK|ANTHROPIC|GOOGLE|EMAIL"`

## ✅ Quick Verification Checklist

- [ ] Python dependencies installed (`pip3 install -r requirements.txt`)
- [ ] Environment variables set in `~/.zshrc`
- [ ] Gmail App Password created and configured
- [ ] Test run successful (`./run_analysis.sh gemini P1`)
- [ ] Real email test successful (`python3 ticket_analyzer.py --llm gemini --priorities P1`)
- [ ] Cron job installed (`crontab -l` shows the entry)
- [ ] Cron wrapper tested (`./cron_wrapper.sh`)

---

## 📦 Portability - Moving to Another Machine

**All scripts are portable!** They auto-detect their location, so you can:

1. **Copy the entire directory** to another machine:
   ```bash
   # On source machine:
   tar -czf ticket-analyzer.tar.gz /path/to/bulk_ticket_export

   # Transfer to new machine, then:
   tar -xzf ticket-analyzer.tar.gz
   cd bulk_ticket_export
   ```

2. **Set up environment variables** on the new machine (Step 1 above)

3. **Install Python dependencies:**
   ```bash
   pip3 install -r requirements.txt
   ```

4. **Test it:**
   ```bash
   ./run_analysis.sh gemini P1
   ```

5. **Install cron job** with the new path (Step 4 above)

**What gets auto-detected:**
- ✅ Script directory location
- ✅ Paths to `zendesk_exporter.py` and output files
- ✅ Log directory location

**What you need to configure:**
- ⚙️ Environment variables (API keys, email credentials)
- ⚙️ Cron job with full path to wrapper script

---

**System is ready! 🚀**

Next Monday at 5 AM Pacific, you'll receive your first automated ticket analysis email.
