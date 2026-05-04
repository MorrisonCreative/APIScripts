#!/bin/bash
# Cron wrapper for automated ticket analysis
# Runs every Monday at 5 AM Pacific Time

# Set timezone to Pacific
export TZ=America/Los_Angeles

# Auto-detect script directory first (needed before sourcing)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load environment variables (API keys, SMTP credentials)
# Source .profile directly to ensure variables are loaded
# Use $HOME which should be set by cron
PROFILE_PATH="$HOME/.profile"
# echo "DEBUG - HOME is: $HOME" >> logs/cron.log
# echo "DEBUG - Looking for profile at: $PROFILE_PATH" >> logs/cron.log
if [ -f "$PROFILE_PATH" ]; then
    # echo "DEBUG - Profile found, sourcing..." >> logs/cron.log
    set -a  # automatically export all variables from .profile
    . "$PROFILE_PATH"
    set +a
    # echo "DEBUG - After sourcing .profile:" >> logs/cron.log
    # echo "  EMAIL_FROM='${EMAIL_FROM}'" >> logs/cron.log
    # echo "  EMAIL_PASSWORD='${EMAIL_PASSWORD:+SET}'" >> logs/cron.log
    # echo "  EMAIL_TO='${EMAIL_TO}'" >> logs/cron.log
else
    echo "ERROR - Profile file not found at $PROFILE_PATH" >> logs/cron.log
fi

# Ensure log directory exists
mkdir -p logs

# Log execution start
echo "========================================" >> logs/cron.log
echo "Execution started at $(date)" >> logs/cron.log
echo "========================================" >> logs/cron.log

# Clean up old exported ticket files
rm -f exported_tickets*.json

# Ensure email variables are exported to subprocesses
export EMAIL_FROM
export EMAIL_PASSWORD
export EMAIL_TO

# Calculate date ranges
END_DATE=$(date +%Y-%m-%d)
WEEK_AGO=$(date -d "7 days ago" +%Y-%m-%d 2>/dev/null || date -v-7d +%Y-%m-%d)
SIX_MONTHS_AGO=$(date -d "180 days ago" +%Y-%m-%d 2>/dev/null || date -v-180d +%Y-%m-%d)

echo "Fetching P1 tickets:" >> logs/cron.log
echo "  1. Created in last 7 days: $WEEK_AGO to $END_DATE" >> logs/cron.log
echo "  2. All open P1 tickets (last 6 months): $SIX_MONTHS_AGO to $END_DATE" >> logs/cron.log

# Export 1: P1 tickets created in the last week (Credential Set 1)
python3 zendesk_exporter.py --start-date "$WEEK_AGO" --end-date "$END_DATE" \
    --priorities P1 --credential-set 1 --format json \
    --output exported_tickets_recent_set1.json 2>&1 | tee -a logs/cron.log

# Export 2: All open P1 tickets (Credential Set 1) - going back 6 months to catch all open tickets
# Note: We'll filter for open status in the ticket data later
python3 zendesk_exporter.py --start-date "$SIX_MONTHS_AGO" --end-date "$END_DATE" \
    --priorities P1 --credential-set 1 --format json \
    --output exported_tickets_all_set1.json 2>&1 | tee -a logs/cron.log

# Export 3: P1 tickets created in the last week (Credential Set 2)
python3 zendesk_exporter.py --start-date "$WEEK_AGO" --end-date "$END_DATE" \
    --priorities P1 --credential-set 2 --format json \
    --output exported_tickets_recent_set2.json 2>&1 | tee -a logs/cron.log

# Export 4: All open P1 tickets (Credential Set 2)
python3 zendesk_exporter.py --start-date "$SIX_MONTHS_AGO" --end-date "$END_DATE" \
    --priorities P1 --credential-set 2 --format json \
    --output exported_tickets_all_set2.json 2>&1 | tee -a logs/cron.log

# Merge and filter tickets using Python
python3 -c "
import json
import sys

def load_json(filepath):
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
            return data.get('tickets', [])
    except:
        return []

def is_p1_and_not_closed(ticket):
    '''Only include tickets that are CURRENTLY P1 and NOT closed/solved'''
    # Check priority is currently P1
    priority = ticket.get('priority', '').upper()
    custom_fields = ticket.get('custom_fields', [])
    priority_field = next((f.get('value', '') for f in custom_fields if 'priority' in str(f.get('id', '')).lower()), '')

    is_p1 = priority == 'P1' or str(priority_field).upper() == 'P1'

    # Check status is NOT closed or solved
    status = ticket.get('status', '').lower()
    is_open = status not in ['closed', 'solved']

    return is_p1 and is_open

# Load all exports
recent_set1 = load_json('exported_tickets_recent_set1.json')
all_set1 = load_json('exported_tickets_all_set1.json')
recent_set2 = load_json('exported_tickets_recent_set2.json')
all_set2 = load_json('exported_tickets_all_set2.json')

# Filter ALL tickets to only include currently P1 and not closed/solved
filtered_recent_set1 = [t for t in recent_set1 if is_p1_and_not_closed(t)]
filtered_all_set1 = [t for t in all_set1 if is_p1_and_not_closed(t)]
filtered_recent_set2 = [t for t in recent_set2 if is_p1_and_not_closed(t)]
filtered_all_set2 = [t for t in all_set2 if is_p1_and_not_closed(t)]

# Combine and deduplicate by ID
all_tickets_set1 = filtered_recent_set1 + [t for t in filtered_all_set1 if t['id'] not in [r['id'] for r in filtered_recent_set1]]
all_tickets_set2 = filtered_recent_set2 + [t for t in filtered_all_set2 if t['id'] not in [r['id'] for r in filtered_recent_set2]]

# Save combined results
with open('exported_tickets_set1.json', 'w') as f:
    json.dump({'tickets': all_tickets_set1, 'ticket_count': len(all_tickets_set1)}, f, indent=2)

with open('exported_tickets_set2.json', 'w') as f:
    json.dump({'tickets': all_tickets_set2, 'ticket_count': len(all_tickets_set2)}, f, indent=2)

print(f'Set 1: {len(filtered_recent_set1)} recent + {len(filtered_all_set1)} historical = {len(all_tickets_set1)} total P1 non-closed/solved (after dedup)')
print(f'Set 2: {len(filtered_recent_set2)} recent + {len(filtered_all_set2)} historical = {len(all_tickets_set2)} total P1 non-closed/solved (after dedup)')
" 2>&1 | tee -a logs/cron.log

# Now run the analyzer on the combined ticket data
python3 ticket_analyzer.py --priorities P1 2>&1 | tee -a logs/cron.log

# Capture exit code
EXIT_CODE=$?

# Log execution end
echo "Execution completed at $(date) with exit code: $EXIT_CODE" >> logs/cron.log
echo "" >> logs/cron.log

# Exit with script's status code
exit $EXIT_CODE
