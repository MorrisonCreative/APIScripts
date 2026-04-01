# Zendesk Ticket Export & Gemini Analyzer - Web Interface

Comprehensive web interface for exporting Zendesk tickets and analyzing them with Gemini AI.

## Features

### 1. Export Tickets
- Select start and end dates
- Filter by organization ID (optional)
- Choose credential set (1 or 2)
- **Fast Mode** (default): Export without full history for 5-10x speedup
- **Full History Mode**: Include all comments/audits (slower)
- Download exported JSON files

### 2. Upload Existing Files
- Upload previously exported ticket JSON files
- Automatic validation and metadata extraction

### 3. Gemini Analysis
- Custom analysis prompts
- Data reduction options for large files:
  - **Full Data**: Send complete ticket data
  - **Key Fields Only**: Extract essential fields (reduces size by ~60-80%)
  - **Filter by Priority**: P1, P2, P3, P4
  - **Filter by Status**: open, pending, solved, etc.
  - **Limit Tickets**: Specify maximum number of tickets
- Real-time analysis progress tracking
- View and save results

## Setup

### 1. Install Requirements
```bash
cd ticketScripts
pip3 install -r requirements_export_analyzer.txt
```

### 2. Set Environment Variables
```bash
# Gemini API Key (required for analysis)
export GOOGLE_API_KEY='your-gemini-api-key'

# Zendesk Credentials - Set 1
export ZENDESK_SUBDOMAIN='your-subdomain'
export ZENDESK_EMAIL='your-email'
export ZENDESK_API_TOKEN='your-token'

# Zendesk Credentials - Set 2 (optional)
export ZENDESK_SUBDOMAIN_2='your-subdomain-2'
export ZENDESK_EMAIL_2='your-email-2'
export ZENDESK_API_TOKEN_2='your-token-2'
```

## Usage

### Start the Web Interface
```bash
./start_export_analyzer.sh
```

Then open http://localhost:5000 in your browser.

### Workflow

**Option A: Export + Analyze**
1. Enter start/end dates
2. Optionally specify organization ID
3. Select credential set
4. **Choose history mode** (leave unchecked for faster exports)
5. Click "Export Tickets"
6. Wait for export to complete
7. Download file (optional)
8. Choose data reduction option
9. Enter analysis prompt
10. Click "Analyze with Gemini"

**Option B: Upload + Analyze**
1. Click "Upload Existing File"
2. Select your JSON file
3. Choose data reduction option
4. Enter analysis prompt
5. Click "Analyze with Gemini"

### Export Performance Guide

**Fast Mode (Recommended):**
- Default setting - leave "Include full ticket history" **unchecked**
- 5-10x faster than full history mode
- Skips fetching complete audit logs and comment history
- Best for: Quick analysis, ticket summaries, status overviews
- Example: 100 tickets in ~1-2 minutes

**Full History Mode:**
- Check "Include full ticket history" checkbox
- Fetches all audits, comments, and history for each ticket
- Adds 0.1s + API calls per ticket
- Best for: Detailed investigations, compliance, full audit trails
- Example: 100 tickets in ~10-15 minutes

### Data Reduction Guide

For files > 800K tokens (~3MB):
- **Recommended**: Use "Key Fields Only" (60-80% size reduction)
- **Alternative**: Filter by priority or limit tickets

### Example Analysis Prompts
- "Summarize all P1 tickets and their current status"
- "Identify common themes and patterns across tickets"
- "List tickets by organization with response times"
- "Analyze which issues took longest to resolve"
- "Find tickets that mention 'API' or 'integration'"

## Files Created

- `ticket_export_analyzer_web.py` - Flask web application
- `templates/ticket_export_analyzer.html` - Web interface
- `requirements_export_analyzer.txt` - Python dependencies
- `start_export_analyzer.sh` - Startup script
- `uploads/` - Uploaded files directory

## Troubleshooting

**"GOOGLE_API_KEY not set"**
- Set the environment variable before starting

**"Token limit exceeded"**
- Use data reduction options
- Try "Key Fields Only" first

**"Export failed"**
- Check Zendesk credentials
- Verify date range is valid
- Check organization ID exists

**"File not found after export"**
- Check logs in terminal
- Files saved to `ticketScripts/` directory

**"Export is very slow"**
- Make sure "Include full ticket history" is **unchecked** (fast mode)
- Full history mode is 5-10x slower
- Reduce date range or use organization filter to export fewer tickets

## Command Line Alternative

For scriptable/automated analysis:
```bash
python3 gemini_ticket_analyzer.py
```

This provides an interactive CLI version with the same data reduction features.
