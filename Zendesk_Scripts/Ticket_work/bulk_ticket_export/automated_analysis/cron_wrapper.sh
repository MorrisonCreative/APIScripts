#!/bin/bash
# Cron wrapper for automated ticket analysis
# Runs every Monday at 5 AM Pacific Time

# Set timezone to Pacific
export TZ=America/Los_Angeles

# Load environment variables (API keys, SMTP credentials)
# Source from shell config
if [ -f ~/.zshrc ]; then
    source ~/.zshrc
fi

# Auto-detect script directory (works on any machine)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Ensure log directory exists
mkdir -p logs

# Log execution start
echo "========================================" >> logs/cron.log
echo "Execution started at $(date)" >> logs/cron.log
echo "========================================" >> logs/cron.log

# Run the analysis (using Gemini, P1 tickets only)
# Remove --priorities flag to get all tickets
python3 ticket_analyzer.py --llm gemini --priorities P1 2>&1 | tee -a logs/cron.log

# Capture exit code
EXIT_CODE=$?

# Log execution end
echo "Execution completed at $(date) with exit code: $EXIT_CODE" >> logs/cron.log
echo "" >> logs/cron.log

# Exit with script's status code
exit $EXIT_CODE
