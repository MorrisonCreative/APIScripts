# APIScripts

A collection of API integration scripts for various platforms.

## Zendesk Ticket Exporter

Export Zendesk tickets by organization, timeframe, or both, with optional full event history (audits and comments).

### Features

- **Three export modes:**
  - Export all tickets for a specific organization
  - Export all tickets across all organizations within a date range (created, updated, or solved)
  - Combined mode: filter by both organization and timeframe
- **Custom priority filtering:**
  - Filter by custom "Ticket Priority" field (P1, P2, P3, P4)
  - Single or multiple priority levels
  - Case-insensitive (handles both uppercase P1 and lowercase p1)
- **Multiple output formats:**
  - JSON format (default) - includes full structure and metadata
  - CSV format - flattened data for spreadsheet analysis
- **Optional full event history** (defaults to yes):
  - Ticket audits (status changes, field updates, assignments)
  - Comments and replies (public and private)
  - Note: CSV format includes counts only, not full history
- **Flexible configuration:**
  - Command-line arguments
  - Environment variables
  - Interactive prompts
- Multiple credential set support for different Zendesk instances
- Automatic pagination handling
- Rate limiting to respect API quotas
- Comprehensive error handling and logging
- Dynamic filename generation based on export parameters
- **Export summary with priority breakdown:**
  - Total ticket count
  - Count per priority level (P1, P2, P3, P4)
  - Unassigned ticket count
  - Priority distribution percentages

### Prerequisites

- Python 3.6 or higher
- Zendesk API token with appropriate permissions
- Required Python packages:
  ```bash
  pip install requests
  ```

### Environment Variables

The following environment variables can be configured:

| Variable | Description | Required | Default | Example |
|----------|-------------|----------|---------|---------|
| `ZENDESK_SUBDOMAIN` | Your Zendesk subdomain (without .zendesk.com) | Yes** | - | `mycompany` |
| `ZENDESK_EMAIL` | Email address associated with the API token | Yes** | - | `admin@example.com` |
| `ZENDESK_API_TOKEN` | Your Zendesk API token | Yes** | - | `abc123xyz789...` |
| `ZENDESK_SUBDOMAIN_2` | Second credential set subdomain | No | - | `production` |
| `ZENDESK_EMAIL_2` | Second credential set email | No | - | `api@example.com` |
| `ZENDESK_API_TOKEN_2` | Second credential set API token | No | - | `def456xyz123...` |
| `ZENDESK_CREDENTIAL_SET` | Select which credential set to use (1 or 2) | No | Auto-detect | `1` or `2` |
| `PRIORITY_FIELD_ID` | Custom field ID for ticket priority (for credential set 1) | No | `360047533253` | `360047533253` |
| `PRIORITY_FIELD_ID_1` | Custom field ID for ticket priority (credential set 1, overrides PRIORITY_FIELD_ID) | No | `360047533253` | `360047533253` |
| `PRIORITY_FIELD_ID_2` | Custom field ID for ticket priority (credential set 2) | No | `360047533253` | `360055678901` |
| `CUSTOMER_ORGANIZATION_ID` | Organization ID to export tickets from | No* | - | `123456789` |
| `START_DATE` | Start date for timeframe exports | No* | - | `2024-01-01` |
| `END_DATE` | End date for timeframe exports | No* | - | `2024-12-31` |
| `DATE_FIELD` | Date field to filter on | No | `created` | `created`, `updated`, `solved` |
| `TICKET_PRIORITIES` | Comma-separated priorities to filter | No | - | `P1,P2` |
| `FETCH_FULL_HISTORY` | Fetch full event history (audits & comments) | No | `true` | `true` or `false` |
| `OUTPUT_FORMAT` | Output file format | No | `json` | `json` or `csv` |
| `OUTPUT_FILE_PATH` | Path where the output file will be saved | No | Auto-generated | `tickets.json` |

\* At least one export mode must be specified (organization ID, date range, or both)
\*\* At least one complete credential set must be configured (Set 1 or Set 2). If both are configured, use `--credential-set` or `ZENDESK_CREDENTIAL_SET` to select which one.

#### Priority Field ID Configuration

The script uses a custom field named "Ticket Priority" to track ticket priorities (P1-P4). Valid priority values are: **P1** (highest), **P2**, **P3**, and **P4** (lowest).

If your Zendesk instance uses a different custom field ID, you can configure it:

**Priority Selection Logic:**

For **Credential Set 1**:
1. `PRIORITY_FIELD_ID_1` (if set) - highest priority
2. `PRIORITY_FIELD_ID` (if set) - fallback
3. Default value: `360047533253`

For **Credential Set 2**:
1. `PRIORITY_FIELD_ID_2` (if set)
2. Default value: `360047533253`

**Example:**
```bash
# Use different priority fields for different Zendesk instances
export PRIORITY_FIELD_ID_1="360047533253"  # Sandbox priority field
export PRIORITY_FIELD_ID_2="360055678901"  # Production priority field
```

**Finding Your Priority Field ID:**
1. Log in to Zendesk Admin
2. Navigate to **Objects and rules** > **Tickets** > **Fields**
3. Click on your priority custom field
4. The ID is in the URL: `https://mycompany.zendesk.com/admin/objects-rules/tickets/ticket-fields/360047533253`

### Setting Environment Variables

#### Temporary (Current Session Only)

**macOS/Linux:**
```bash
export ZENDESK_SUBDOMAIN="mycompany"
export ZENDESK_EMAIL="admin@example.com"
export ZENDESK_API_TOKEN="your_api_token_here"
export PRIORITY_FIELD_ID="360047533253"
export CUSTOMER_ORGANIZATION_ID="123456789"
export FETCH_FULL_HISTORY="true"
export OUTPUT_FILE_PATH="exported_tickets.json"
```

**Windows (Command Prompt):**
```cmd
set ZENDESK_SUBDOMAIN=mycompany
set ZENDESK_EMAIL=admin@example.com
set ZENDESK_API_TOKEN=your_api_token_here
set PRIORITY_FIELD_ID=360047533253
set CUSTOMER_ORGANIZATION_ID=123456789
set FETCH_FULL_HISTORY=true
set OUTPUT_FILE_PATH=exported_tickets.json
```

**Windows (PowerShell):**
```powershell
$env:ZENDESK_SUBDOMAIN="mycompany"
$env:ZENDESK_EMAIL="admin@example.com"
$env:ZENDESK_API_TOKEN="your_api_token_here"
$env:PRIORITY_FIELD_ID="360047533253"
$env:CUSTOMER_ORGANIZATION_ID="123456789"
$env:FETCH_FULL_HISTORY="true"
$env:OUTPUT_FILE_PATH="exported_tickets.json"
```

#### Permanent Configuration

**macOS/Linux (bash):**

1. Open your bash profile:
   ```bash
   nano ~/.bash_profile
   # or for newer macOS versions
   nano ~/.zprofile
   ```

2. Add the export commands:
   ```bash
   export ZENDESK_SUBDOMAIN="mycompany"
   export ZENDESK_EMAIL="admin@example.com"
   export ZENDESK_API_TOKEN="your_api_token_here"
   export PRIORITY_FIELD_ID="360047533253"
   export CUSTOMER_ORGANIZATION_ID="123456789"
   export FETCH_FULL_HISTORY="true"
   export OUTPUT_FILE_PATH="exported_tickets.json"
   ```

3. Save and reload:
   ```bash
   source ~/.bash_profile
   # or
   source ~/.zprofile
   ```

**macOS/Linux (zsh):**

1. Open your zsh profile:
   ```bash
   nano ~/.zshrc
   ```

2. Add the export commands (same as above)

3. Save and reload:
   ```bash
   source ~/.zshrc
   ```

**Windows (Permanent System Variables):**

1. Open System Properties:
   - Press `Win + X` and select "System"
   - Click "Advanced system settings"
   - Click "Environment Variables"

2. Under "User variables" or "System variables", click "New"

3. Add each variable:
   - Variable name: `ZENDESK_SUBDOMAIN`
   - Variable value: `mycompany`
   - Repeat for all variables

4. Click "OK" to save

**Using a .env file (Recommended for Security):**

1. Create a `.env` file in the project directory:
   ```bash
   nano .env
   ```

2. Add your variables:
   ```
   ZENDESK_SUBDOMAIN=mycompany
   ZENDESK_EMAIL=admin@example.com
   ZENDESK_API_TOKEN=your_api_token_here
   PRIORITY_FIELD_ID=360047533253
   CUSTOMER_ORGANIZATION_ID=123456789
   FETCH_FULL_HISTORY=true
   OUTPUT_FILE_PATH=exported_tickets.json
   ```

3. Install python-dotenv:
   ```bash
   pip install python-dotenv
   ```

4. Add to the top of `zendesk_exporter.py` (before other imports):
   ```python
   from dotenv import load_dotenv
   load_dotenv()
   ```

5. **Important:** Add `.env` to your `.gitignore` to prevent committing secrets:
   ```bash
   echo ".env" >> .gitignore
   ```

### Getting Your Zendesk API Token

1. Log in to your Zendesk account
2. Click the **Admin** icon (gear icon) in the sidebar
3. Navigate to **Apps and integrations** > **APIs** > **Zendesk API**
4. Click the **Settings** tab
5. Enable **Token Access**
6. Click the **+** button to create a new token
7. Copy the token (it will only be shown once)

### Command-Line Arguments

The script supports command-line arguments that override environment variables:

```bash
python zendesk_exporter.py [OPTIONS]
```

**Options:**

| Argument | Description | Example |
|----------|-------------|---------|
| `--start-date` | Start date (YYYY-MM-DD) | `--start-date 2024-01-01` |
| `--end-date` | End date (YYYY-MM-DD) | `--end-date 2024-12-31` |
| `--date-field` | Date field to filter on | `--date-field updated` |
| `--priorities` | Comma-separated priorities (P1,P2,P3,P4) | `--priorities P1,P2` |
| `--organization-id` | Organization ID (optional - omit to search all organizations) | `--organization-id 123456` |
| `--credential-set` | Select credential set (1 or 2) | `--credential-set 2` |
| `--format` | Output file format (json or csv) | `--format csv` |
| `--no-history` | Skip fetching full event history | `--no-history` |
| `--output` | Output file path | `--output tickets.json` |

### Usage

#### Mode 1: Export by Organization (Backward Compatible)

**Using CLI arguments:**
```bash
python zendesk_exporter.py --organization-id 123456
```

**Using environment variables:**
```bash
export ZENDESK_SUBDOMAIN="mycompany"
export ZENDESK_EMAIL="admin@example.com"
export ZENDESK_API_TOKEN="your_token"
export CUSTOMER_ORGANIZATION_ID="123456789"
export FETCH_FULL_HISTORY="true"

python zendesk_exporter.py
```

**Interactive mode:**
```bash
python zendesk_exporter.py
# Select mode (1) By organization
# Enter organization ID when prompted
```

#### Mode 2: Export by Timeframe (All Organizations)

Export tickets across all organizations in your Zendesk instance within a specified timeframe.

**Export all tickets from Q1 2024 (across all organizations):**
```bash
python zendesk_exporter.py \
  --start-date 2024-01-01 \
  --end-date 2024-03-31
```

**Export P1 priority tickets from January (all organizations):**
```bash
python zendesk_exporter.py \
  --start-date 2024-01-01 \
  --end-date 2024-01-31 \
  --priorities P1
```

**Export P1 and P2 tickets updated in the last month:**
```bash
python zendesk_exporter.py \
  --start-date 2024-02-01 \
  --end-date 2024-02-29 \
  --date-field updated \
  --priorities P1,P2
```

**Using environment variables:**
```bash
export ZENDESK_SUBDOMAIN="mycompany"
export ZENDESK_EMAIL="admin@example.com"
export ZENDESK_API_TOKEN="your_token"
export START_DATE="2024-01-01"
export END_DATE="2024-12-31"
export TICKET_PRIORITIES="P1,P2"

python zendesk_exporter.py
```

#### Mode 3: Combined (Organization + Timeframe)

**Export P1 tickets from specific organization in January:**
```bash
python zendesk_exporter.py \
  --organization-id 123456 \
  --start-date 2024-01-01 \
  --end-date 2024-01-31 \
  --priorities P1 \
  --output high_priority_jan.json
```

**Export tickets without full history (faster):**
```bash
python zendesk_exporter.py \
  --start-date 2024-01-01 \
  --end-date 2024-01-31 \
  --no-history
```

#### CSV Export

**Export to CSV format for spreadsheet analysis:**
```bash
python zendesk_exporter.py \
  --start-date 2024-01-01 \
  --end-date 2024-01-31 \
  --format csv
```

**CSV with priority filter:**
```bash
python zendesk_exporter.py \
  --start-date 2024-01-01 \
  --end-date 2024-03-31 \
  --priorities P1,P2 \
  --format csv \
  --output q1_priority_tickets.csv
```

**Important CSV Notes:**
- CSV format includes main ticket fields and custom priority
- Audit and comment counts are included (if `--no-history` not used)
- Full audit/comment history is NOT included in CSV (use JSON for that)
- Tags are comma-separated within a single CSV cell
- Suitable for Excel, Google Sheets, or data analysis tools

#### Interactive Mode

Run without arguments to be prompted for configuration:

```bash
python zendesk_exporter.py
```

You'll be prompted for:
1. Export mode selection (organization, timeframe, or both)
2. Required parameters based on selected mode
3. Optional priority filter
4. Whether to fetch full event history

### Multiple Credential Sets

The script supports configuring two sets of Zendesk credentials for working with multiple instances (e.g., sandbox and production).

#### Setup

**Configure Set 1 (Primary):**
```bash
export ZENDESK_SUBDOMAIN="sandbox"
export ZENDESK_EMAIL="test@example.com"
export ZENDESK_API_TOKEN="token123"
export PRIORITY_FIELD_ID_1="360047533253"  # Optional: custom field for sandbox
```

**Configure Set 2 (Secondary):**
```bash
export ZENDESK_SUBDOMAIN_2="production"
export ZENDESK_EMAIL_2="api@example.com"
export ZENDESK_API_TOKEN_2="token456"
export PRIORITY_FIELD_ID_2="360055678901"  # Optional: custom field for production
```

#### Usage

**Auto-selection (when only one set is configured):**
```bash
# If only Set 1 is configured, it's automatically used
python zendesk_exporter.py --organization-id 12345
```

**Explicit selection via CLI:**
```bash
# Use Set 1 (sandbox)
python zendesk_exporter.py --credential-set 1 --organization-id 12345

# Use Set 2 (production)
python zendesk_exporter.py --credential-set 2 --organization-id 67890
```

**Explicit selection via environment variable:**
```bash
export ZENDESK_CREDENTIAL_SET=2
python zendesk_exporter.py --organization-id 12345
```

**CLI overrides environment variable:**
```bash
export ZENDESK_CREDENTIAL_SET=1
# This uses Set 2, not Set 1
python zendesk_exporter.py --credential-set 2 --organization-id 12345
```

#### Behavior

- **One set configured:** Automatically selected, no action needed
- **Both sets configured:** Must specify which to use via `--credential-set` or `ZENDESK_CREDENTIAL_SET`
- **Neither set configured:** Error with instructions
- **Incomplete set:** Error listing missing variables

The script logs which credential set is active:
```
INFO - Using credential set 1: sandbox (test@example.com)
```

### Output Format

The script generates a JSON file with the following structure:

**Organization-only export (backward compatible):**
```json
[
  {
    "id": 12345,
    "url": "https://mycompany.zendesk.com/api/v2/tickets/12345.json",
    "subject": "Customer inquiry",
    "description": "Initial ticket description",
    "status": "open",
    "priority": "normal",
    "type": "question",
    "created_at": "2026-01-15T10:30:00Z",
    "updated_at": "2026-01-16T14:20:00Z",
    "organization_id": 123456789,
    "requester_id": 987654321,
    "assignee_id": 111222333,
    "tags": ["customer", "inquiry"],
    "custom_fields": [
      {
        "id": 360047533253,
        "value": "P1"
      }
    ]
  }
]
```

**Timeframe export (with metadata):**
```json
{
  "export_metadata": {
    "export_date": "2024-03-15T14:30:22.123456",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "date_field": "created",
    "ticket_priorities": ["P1", "P2"],
    "priority_field_id": "360047533253",
    "organization_id": null,
    "total_tickets": 1523,
    "priority_breakdown": {
      "P1": 342,
      "P2": 789,
      "P3": 312,
      "P4": 68,
      "unassigned": 12
    },
    "includes_history": true
  },
  "tickets": [
    {
      "id": 12345,
      "subject": "Customer inquiry",
      "status": "open",
      "custom_fields": [
        {
          "id": 360047533253,
          "value": "P1"
        }
      ],
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-16T14:20:00Z"
    }
  ]
}
```

**Full export (with event history):**
```json
[
  {
    "id": 12345,
    "subject": "Customer inquiry",
    "status": "open",
    "...": "... (all metadata fields)",
    "audits": [
      {
        "id": 67890,
        "ticket_id": 12345,
        "created_at": "2026-01-15T10:30:00Z",
        "author_id": 111222333,
        "events": [
          {
            "id": 98765,
            "type": "Create",
            "field_name": "status",
            "value": "new"
          },
          {
            "id": 98766,
            "type": "Change",
            "field_name": "status",
            "previous_value": "new",
            "value": "open"
          }
        ]
      }
    ],
    "comments": [
      {
        "id": 11111,
        "type": "Comment",
        "author_id": 987654321,
        "body": "Thank you for contacting support...",
        "html_body": "<p>Thank you for contacting support...</p>",
        "plain_body": "Thank you for contacting support...",
        "public": true,
        "created_at": "2026-01-15T10:35:00Z"
      }
    ]
  }
]
```

**CSV export format:**

CSV files contain flattened ticket data suitable for spreadsheet analysis:

| id | subject | status | priority | type | created_at | ticket_priority | tags | audit_count | comment_count |
|----|---------|--------|----------|------|------------|-----------------|------|-------------|---------------|
| 12345 | Customer inquiry | open | high | question | 2024-01-15T10:30:00Z | P1 | urgent,customer | 5 | 3 |
| 12346 | Feature request | pending | normal | task | 2024-01-16T14:20:00Z | P2 | feature,roadmap | 2 | 1 |

**CSV Columns:**
- **Basic fields**: id, subject, description, status, priority, type
- **Timestamps**: created_at, updated_at
- **Relationships**: organization_id, requester_id, assignee_id, submitter_id, group_id
- **Custom fields**: ticket_priority (from custom field 360047533253)
- **Tags**: Comma-separated list in single cell
- **History counts**: audit_count, comment_count (if history was fetched)
- **URL**: Direct link to ticket

**Note:** CSV format does not include nested structures (full audit events, comment bodies). Use JSON format for complete data preservation.

### Dynamic Filenames

When no output path is specified, the script generates descriptive filenames based on export parameters:

- **Organization-only**: `tickets_org_123456_20240315_143022.json`
- **Timeframe-only**: `tickets_2024-01-01_to_2024-12-31_20240315_143022.json`
- **With priorities**: `tickets_2024-01-01_to_2024-12-31_P1-P2_20240315_143022.json`
- **Combined**: `tickets_2024-01-01_to_2024-12-31_P1_org_123456_20240315_143022.json`
- **CSV format**: `tickets_2024-01-01_to_2024-12-31_P1-P2_20240315_143022.csv`

The file extension (.json or .csv) is automatically set based on the selected format.

### Export Summary

After fetching tickets, the script displays a comprehensive summary in the console:

```
============================================================
EXPORT SUMMARY
============================================================
Total Tickets Exported: 1523

Priority Breakdown:
  P1 (Highest):   342 tickets
  P2:             789 tickets
  P3:             312 tickets
  P4 (Lowest):     68 tickets
  Unassigned:      12 tickets

Priority Distribution (of assigned tickets):
  P1:  22.6%
  P2:  52.2%
  P3:  20.6%
  P4:   4.5%
============================================================
```

**Summary includes:**
- **Total Tickets Exported**: Overall count of tickets exported
- **Priority Breakdown**: Count of tickets for each priority level (P1-P4)
- **Unassigned**: Tickets without a priority value set
- **Priority Distribution**: Percentage breakdown of assigned tickets

**Notes:**
- The summary appears after all tickets are fetched and enriched (if applicable)
- For JSON exports with timeframe mode, the breakdown is also saved in the `priority_breakdown` field of the export metadata
- Percentages are calculated only from tickets with assigned priorities (excludes unassigned tickets)
- If no tickets are exported, only the total count is shown

### Performance Considerations

- **Metadata only** (`--no-history`): Fast, ~1-2 API calls per 100 tickets
- **Full history** (default): Slower, ~200 API calls per 100 tickets
  - 10 tickets: ~2-3 seconds
  - 100 tickets: ~20-30 seconds
  - 1,000 tickets: ~3-5 minutes

The script includes automatic rate limiting (0.1s delay between requests) to respect Zendesk API quotas.

**Tip:** Use `--no-history` for faster exports when you only need ticket metadata.

### Troubleshooting

#### Authentication Errors

```
HTTP Error during Zendesk API request: 401 - Unauthorized
```

**Solution:** Verify your credentials:
- Check that `ZENDESK_EMAIL` is correct
- Ensure `ZENDESK_API_TOKEN` is valid (regenerate if needed)
- Confirm token access is enabled in Zendesk Admin settings

#### Invalid Organization ID

```
Invalid organization ID: abc123. Organization ID must be numeric.
```

**Solution:** Organization ID must be a number. Find it by:
1. Going to Zendesk Admin > Customers > Organizations
2. Clicking on the organization
3. The ID is in the URL: `https://mycompany.zendesk.com/agent/organizations/123456789`

#### Rate Limiting

```
HTTP Error during Zendesk API request: 429 - Too Many Requests
```

**Solution:** The script includes rate limiting, but if you still hit limits:
- Wait a few minutes before running again
- Consider exporting in smaller batches
- Contact Zendesk to increase your rate limit

#### Permission Errors

```
HTTP Error during Zendesk API request: 403 - Forbidden
```

**Solution:** Your API token doesn't have permission to access the requested resource:
- Verify the token has read access to tickets
- Check that your user account has permission to view the organization's tickets
- Contact your Zendesk admin to grant necessary permissions

#### Invalid Date Format

```
Validation error: Invalid date format: 01/15/2024. Use YYYY-MM-DD or ISO 8601 format.
```

**Solution:** Use the correct date format:
- `YYYY-MM-DD`: `2024-01-15`
- ISO 8601: `2024-01-15T10:30:00Z`

#### Invalid Priority Values

```
Validation error: Invalid priority values: ['P5', 'HIGH']. Valid values: ['P1', 'P2', 'P3', 'P4']
```

**Solution:** Use only valid priority values: P1, P2, P3, or P4
- Case-insensitive: `P1`, `p1`, `P1` are all valid
- Comma-separated for multiple: `P1,P2,P3`

#### Date Range Error

```
Validation error: Start date (2024-12-31) must be before or equal to end date (2024-01-01)
```

**Solution:** Ensure start date is before or equal to end date

#### Multiple Credential Sets - No Selection

```
ERROR - Multiple credential sets detected. Please specify which to use:
ERROR -   --credential-set 1  (or set ZENDESK_CREDENTIAL_SET=1)
ERROR -   --credential-set 2  (or set ZENDESK_CREDENTIAL_SET=2)
```

**Solution:** When both credential sets are configured, you must specify which one to use:
```bash
# Via CLI
python zendesk_exporter.py --credential-set 1 --organization-id 12345

# Via environment variable
export ZENDESK_CREDENTIAL_SET=2
python zendesk_exporter.py --organization-id 12345
```

#### Incomplete Credential Set

```
ERROR - Credential set 2 is incomplete. Missing: ['api_token']
ERROR - Required: ZENDESK_SUBDOMAIN_2, ZENDESK_EMAIL_2, ZENDESK_API_TOKEN_2
```

**Solution:** Ensure all three variables are set for the selected credential set:
```bash
export ZENDESK_SUBDOMAIN_2="production"
export ZENDESK_EMAIL_2="api@example.com"
export ZENDESK_API_TOKEN_2="your_token_here"
```

#### Invalid Credential Set Value

```
ERROR - Credential set error: Invalid credential set: 3. Must be 1 or 2.
```

**Solution:** Only values 1 or 2 are valid:
```bash
python zendesk_exporter.py --credential-set 1  # or 2
```

### Security Best Practices

1. **Never commit API tokens to version control**
   - Add `.env` to `.gitignore`
   - Use environment variables or secure secret management

2. **Rotate tokens regularly**
   - Generate new tokens periodically
   - Revoke old tokens after updating

3. **Limit token permissions**
   - Use the minimum required permissions (read-only for exports)
   - Create separate tokens for different purposes

4. **Secure exported data**
   - Exported JSON files contain sensitive customer data
   - Store in secure locations with appropriate access controls
   - Delete after processing if no longer needed

### Finding Your Organization ID

**Method 1: Via Zendesk Admin UI**
1. Log in to Zendesk
2. Click **Admin** (gear icon)
3. Navigate to **Customers** > **Organizations**
4. Click on the organization you want to export
5. The URL will show the ID: `https://mycompany.zendesk.com/agent/organizations/123456789`

**Method 2: Via API**
```bash
curl -u your_email@example.com/token:your_api_token \
  https://mycompany.zendesk.com/api/v2/organizations.json
```

**Method 3: Search by name**
```bash
curl -u your_email@example.com/token:your_api_token \
  "https://mycompany.zendesk.com/api/v2/organizations/search.json?name=Organization%20Name"
```

### License

MIT License

### Support

For issues or questions:
1. Check the troubleshooting section above
2. Review Zendesk API documentation: https://developer.zendesk.com/api-reference/
3. Open an issue in this repository
