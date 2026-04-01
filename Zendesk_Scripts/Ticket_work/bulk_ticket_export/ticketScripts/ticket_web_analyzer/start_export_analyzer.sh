#!/bin/bash
# Start Zendesk Ticket Export & Analyzer Web Interface

echo "=========================================="
echo "Zendesk Ticket Export & Analyzer"
echo "=========================================="
echo ""

# Check for required environment variables
if [ -z "$GOOGLE_API_KEY" ]; then
    echo "⚠️  WARNING: GOOGLE_API_KEY not set"
    echo "   Set it with: export GOOGLE_API_KEY='your-key-here'"
    echo ""
fi

if [ -z "$ZENDESK_SUBDOMAIN" ]; then
    echo "⚠️  WARNING: Zendesk credentials not set"
    echo "   Set ZENDESK_SUBDOMAIN, ZENDESK_EMAIL, ZENDESK_API_TOKEN"
    echo ""
fi

# Install requirements if needed
if ! python3 -c "import flask" 2>/dev/null; then
    echo "Installing requirements..."
    pip3 install -r requirements_export_analyzer.txt
    echo ""
fi

# Start the web interface
echo "Starting web server..."
echo "Open http://localhost:5000 in your browser"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python3 ticket_export_analyzer_web.py
