# Zendesk Ticket Web Analyzer

Complete web-based interface for exporting Zendesk tickets and analyzing them with Gemini AI.

## What's In This Directory

This is a **self-contained** web application with everything needed to export and analyze Zendesk tickets.

### Core Files

```
ticket_web_analyzer/
├── ticket_export_analyzer_web.py    # Flask web server (main application)
├── zendesk_exporter.py              # Zendesk API export script
├── gemini_ticket_analyzer.py        # CLI version (alternative interface)
├── templates/
│   └── ticket_export_analyzer.html  # Web UI (HTML/CSS/JavaScript)
├── uploads/                         # Auto-created for file uploads
├── start_export_analyzer.sh         # Quick start script
├── requirements_export_analyzer.txt # Python dependencies
├── EXPORT_ANALYZER_README.md        # Full documentation
└── README.md                        # This file
```

## Quick Start

### 1. Install Dependencies
```bash
pip3 install -r requirements_export_analyzer.txt
```

### 2. Set Environment Variables
```bash
# Required for analysis
export GOOGLE_API_KEY='your-gemini-api-key'

# Required for export
export ZENDESK_SUBDOMAIN='your-subdomain'
export ZENDESK_EMAIL='your-email@example.com'
export ZENDESK_API_TOKEN='your-api-token'

# Optional - Second Zendesk instance
export ZENDESK_SUBDOMAIN_2='your-subdomain-2'
export ZENDESK_EMAIL_2='your-email-2@example.com'
export ZENDESK_API_TOKEN_2='your-api-token-2'
```

### 3. Start the Web Interface
```bash
cd ticket_web_analyzer
./start_export_analyzer.sh
```

Then open: **http://localhost:5000**

## Features

### 1. Export Tickets
- Select date range
- Filter by organization (optional)
- Choose credential set
- **Fast mode** (default): 5-10x faster, skips full history
- **Full history mode**: Includes all comments/audits
- Shows ticket count, file size, priority breakdown
- Download exported JSON files

### 2. Upload Existing Files
- Upload previously exported ticket JSON files
- Automatic validation and metadata extraction

### 3. Gemini AI Analysis
- Custom analysis prompts
- Markdown-formatted output with proper rendering
- Data reduction options for large files:
  - Full data
  - Key fields only (60-80% smaller)
  - Filter by priority (P1, P2, P3, P4)
  - Filter by status (open, pending, solved)
  - Limit ticket count

## Usage Examples

### Export Workflow
1. Enter start/end dates (e.g., 2026-03-01 to 2026-04-01)
2. (Optional) Enter organization ID
3. Select credential set
4. **Leave "Include full ticket history" unchecked** for fast export
5. Click "Export Tickets"
6. Wait 5-15 seconds for small datasets
7. Download file or proceed to analysis

### Analysis Workflow
1. After export or upload
2. Choose data reduction option (use "Key Fields Only" for large files)
3. Enter analysis prompt, examples:
   - "Summarize all P1 tickets and their current status"
   - "Identify common themes and patterns"
   - "List tickets by organization with response times"
   - "Find tickets mentioning 'API' or 'integration'"
4. Click "Analyze with Gemini"
5. View beautifully formatted markdown results

## Performance

### Fast Mode (Recommended)
- **16 tickets**: ~5-15 seconds
- **100 tickets**: ~1-2 minutes
- Best for: Quick analysis, status overviews, summaries

### Full History Mode
- **16 tickets**: ~30-60 seconds  
- **100 tickets**: ~10-15 minutes
- Best for: Detailed investigations, compliance, audit trails

## Troubleshooting

**Port already in use:**
```bash
lsof -ti:5000 | xargs kill
./start_export_analyzer.sh
```

**Export very slow:**
- Make sure "Include full ticket history" is **unchecked**
- Reduce date range
- Filter by organization

**"Token limit exceeded" error:**
- Use "Key Fields Only" option (60-80% reduction)
- Or filter by priority/status
- Or limit number of tickets

**Environment variables not found:**
```bash
# Check if set
env | grep ZENDESK
env | grep GOOGLE_API_KEY

# Re-export them in current terminal
source ~/.zshrc  # or ~/.bashrc
```

## File Descriptions

### ticket_export_analyzer_web.py
- Flask web server on port 5000
- API endpoints for export, upload, analysis
- Handles background jobs with threading
- Calls zendesk_exporter.py as subprocess
- Calls Gemini API for analysis
- Extracts metadata (ticket counts, file size, priorities)

### zendesk_exporter.py
- Core Zendesk API export script
- Supports `--no-history` flag for fast exports
- Handles authentication and pagination
- Exports to JSON format
- Includes priority breakdown

### ticket_export_analyzer.html
- Complete web UI
- Uses marked.js for markdown rendering
- Uses DOMPurify for HTML sanitization
- Real-time status updates with polling
- Beautiful CSS styling for analysis results

### gemini_ticket_analyzer.py
- Command-line alternative to web interface
- Interactive prompts for file and prompt
- Same data reduction options
- Good for scripting/automation

## Architecture

```
Browser (port 5000)
    ↓
ticket_export_analyzer_web.py (Flask)
    ↓
    ├── subprocess → zendesk_exporter.py → Zendesk API
    └── HTTP → Gemini API
```

## Security Notes

- Uses DOMPurify to sanitize HTML from Gemini
- Environment variables for credentials (not in code)
- File uploads restricted to JSON
- 100MB max file upload size

## Advanced: Hosting

To keep running permanently, see hosting options in EXPORT_ANALYZER_README.md:
- macOS: launchd
- Linux: systemd
- Docker
- Cloud hosting (Heroku, Railway, etc.)

## Alternative CLI Tool

Don't need a web interface? Use the CLI version:
```bash
python3 gemini_ticket_analyzer.py
```

Interactive prompts guide you through:
1. Select ticket JSON file
2. Choose data reduction option
3. Enter analysis prompt
4. View results

## Support

For issues or questions:
- Check EXPORT_ANALYZER_README.md for detailed documentation
- Review logs in terminal where web server is running
- Check browser console for JavaScript errors

## Version Info

- Flask web server on Python 3.9+
- Gemini 2.5 Flash model
- Marked.js v11.0.0 for markdown
- DOMPurify v3.0.8 for sanitization
