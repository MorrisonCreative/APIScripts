# Design Plan: Zendesk Timeframe-Based Ticket Export Script

## Overview
Design for a new Python script that exports all Zendesk tickets within a specified timeframe and optional custom priority filter. This script will be based on the architecture of the existing `zendesk_exporter.py` but modified to support date range and custom field priority filtering.

## Script Name
`zendesk_timeframe_exporter.py`

---

## Core Requirements

### 1. Date Range Filtering
- Accept **start date** and **end date** parameters
- Support multiple date field options:
  - `created_at` (ticket creation date) - DEFAULT
  - `updated_at` (last update date)
  - `solved_at` (ticket resolution date)
- Date format: ISO 8601 format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ)
- Validation: Ensure start_date <= end_date

### 2. Custom Field Priority Filtering
- **Custom Field:** "Ticket Priority"
- **Field ID:** 360047533253
- Support filtering by priority values:
  - `P1` (highest priority)
  - `P2`
  - `P3`
  - `P4` (lowest priority)
- Allow multiple priorities (e.g., "P1,P2")
- Make priority filtering optional (export all priorities if not specified)
- Query using custom field syntax: `custom_field_360047533253:P1`

### 3. Additional Features
- Maintain all existing features from `zendesk_exporter.py`:
  - Optional enrichment with audits and comments (**DEFAULT: YES**)
  - Pagination handling
  - Rate limiting
  - Comprehensive error handling
  - Progress logging

---

## Architecture

### Class Structure

#### `ZendeskAPIClient` (Reuse/Extend)
Extend the existing `ZendeskAPIClient` class with new method:

```python
def search_tickets_by_timeframe(self, start_date, end_date,
                                date_field="created",
                                ticket_priorities=None,
                                additional_filters=None)
```

**Parameters:**
- `start_date` (str): Start date in ISO format
- `end_date` (str): End date in ISO format
- `date_field` (str): Which date field to filter on ("created", "updated", "solved")
- `ticket_priorities` (list): List of priority levels to include (P1, P2, P3, P4) - optional
- `additional_filters` (str): Additional Zendesk query parameters (optional)

**Query Construction:**
Use Zendesk Search API with custom field query syntax:
```
type:ticket created>=2024-01-01 created<=2024-12-31 custom_field_360047533253:P1 custom_field_360047533253:P2
```

**Pagination:**
- Use same pagination approach as existing script
- Handle up to 100 results per page
- Continue until no more results

---

## Configuration

### Environment Variables
```bash
# Authentication (same as existing)
ZENDESK_SUBDOMAIN=your-subdomain
ZENDESK_EMAIL=your-email@example.com
ZENDESK_API_TOKEN=your-api-token

# New configuration options
START_DATE=2024-01-01                    # Required if not provided via input
END_DATE=2024-12-31                      # Required if not provided via input
DATE_FIELD=created                       # Optional: created, updated, solved (default: created)
TICKET_PRIORITIES=P1,P2                  # Optional: comma-separated list (P1, P2, P3, P4)
FETCH_FULL_HISTORY=true                  # Optional: true/false (default: true)
OUTPUT_FILE_PATH=tickets_export.json     # Optional: default naming with timestamp
```

### Command-Line Arguments (Alternative/Override)
Provide option to use command-line arguments that override environment variables:
```bash
python zendesk_timeframe_exporter.py \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  --date-field created \
  --priorities P1,P2 \
  --no-history \
  --output tickets_export.json
```

### Interactive Prompts (Fallback)
If configuration not provided, prompt user for:
1. Start date (required)
2. End date (required)
3. Date field to filter on (optional, default: created)
4. Ticket Priority levels - P1, P2, P3, P4 (optional, skip for all)
5. Fetch full history (yes/no, **default: yes**)

---

## Implementation Details

### Date Handling
```python
from datetime import datetime
import dateutil.parser

def validate_and_parse_date(date_string):
    """Parse and validate date string"""
    try:
        parsed = dateutil.parser.parse(date_string)
        return parsed.strftime("%Y-%m-%d")
    except:
        raise ValueError(f"Invalid date format: {date_string}")
```

### Priority Validation
```python
VALID_PRIORITIES = ["P1", "P2", "P3", "P4"]
PRIORITY_FIELD_ID = "360047533253"

def validate_priorities(priority_string):
    """Validate and parse priority string"""
    if not priority_string:
        return None

    priorities = [p.strip().upper() for p in priority_string.split(",")]
    invalid = [p for p in priorities if p not in VALID_PRIORITIES]

    if invalid:
        raise ValueError(f"Invalid priority values: {invalid}. Valid values: {VALID_PRIORITIES}")

    return priorities
```

### Query Builder
```python
def build_search_query(start_date, end_date, date_field, ticket_priorities):
    """Build Zendesk search query string with custom field priority"""
    query_parts = ["type:ticket"]

    # Date range
    query_parts.append(f"{date_field}>={start_date}")
    query_parts.append(f"{date_field}<={end_date}")

    # Custom field priorities (if specified)
    if ticket_priorities:
        # Build query for custom field 360047533253
        priority_queries = [f"custom_field_{PRIORITY_FIELD_ID}:{p}"
                           for p in ticket_priorities]
        # Use OR logic for multiple priorities
        priority_query = " ".join(priority_queries)
        query_parts.append(f"({priority_query})")

    return " ".join(query_parts)

# Example query output:
# type:ticket created>=2024-01-01 created<=2024-12-31 (custom_field_360047533253:P1 custom_field_360047533253:P2)
```

### Configuration Loading with Default
```python
# Fetch full history defaults to True
FETCH_FULL_HISTORY = os.getenv("FETCH_FULL_HISTORY", "true").lower() in ["true", "1", "yes"]

if FETCH_FULL_HISTORY is None:
    try:
        response = input("Fetch full event history (audits & comments)? [Y/n]: ").strip().lower()
        FETCH_FULL_HISTORY = response != "n" and response != "no"
    except KeyboardInterrupt:
        logging.info("\nOperation cancelled by user.")
        sys.exit(0)
```

### Rate Limiting Strategy
- Maintain existing 0.1 second delay for enrichment requests
- Monitor response headers for rate limit information
- Implement exponential backoff on 429 (Too Many Requests) responses

### Progress Tracking
Enhanced logging with:
- Estimated total tickets (if available from search metadata)
- Current page number
- Tickets fetched so far
- Estimated time remaining for enrichment
- Percentage complete

---

## Output Format

### File Naming
Default output filename includes timestamp and filter info:
```
tickets_{start_date}_to_{end_date}_{priorities}_{timestamp}.json
```
Example: `tickets_2024-01-01_to_2024-12-31_P1-P2_20240315_143022.json`

### JSON Structure
```json
{
  "export_metadata": {
    "export_date": "2024-03-15T14:30:22Z",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "date_field": "created",
    "ticket_priorities": ["P1", "P2"],
    "priority_field_id": "360047533253",
    "total_tickets": 1523,
    "includes_history": true
  },
  "tickets": [
    {
      "id": 12345,
      "subject": "Ticket subject",
      "status": "open",
      "custom_fields": [
        {
          "id": 360047533253,
          "value": "P1"
        }
      ],
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-16T14:22:00Z",
      "audits": [...],
      "comments": [...]
    }
  ]
}
```

---

## Error Handling

### Input Validation Errors
- Invalid date formats
- Start date after end date
- Invalid priority values (not P1, P2, P3, or P4)
- Invalid date_field values

### API Errors
- Authentication failures (401)
- Rate limiting (429) - implement retry with backoff
- Connection errors - log and exit gracefully
- Timeout errors - log and offer to retry
- Invalid query syntax (422) - provide helpful error message about custom field

### File I/O Errors
- Permissions issues on output file
- Disk space issues
- Path not found

---

## Testing Strategy

### Unit Tests
- Date validation and parsing
- Priority validation (P1-P4)
- Query builder with custom field syntax
- Priority list parsing
- Configuration loading from env vars

### Integration Tests
Test script against Zendesk sandbox:
1. Small date range (1 day, few tickets)
2. Large date range (1 year, many tickets)
3. Single priority filter (P1 only)
4. Multiple priority filters (P1, P2)
5. No priority filter (all tickets regardless of priority)
6. With full history enrichment (default behavior)
7. Without full history enrichment (opt-out)
8. Different date fields (created, updated, solved)
9. Tickets with no priority value set

### Edge Cases
- Zero tickets in timeframe
- Tickets with null/missing custom field value
- Very large result sets (1000+ tickets)
- API rate limiting scenarios
- Network interruption during export
- Custom field not populated on some tickets

---

## Performance Considerations

### Optimization Strategies
1. **Batch API calls where possible**
   - Current enrichment is sequential; maintain for reliability
   - Consider parallel requests if rate limits allow

2. **Memory management**
   - For very large exports (10k+ tickets), consider:
     - Streaming write to file (write tickets as fetched)
     - Chunked exports (export in date ranges)

3. **Resume capability**
   - Save progress periodically
   - Allow resuming interrupted exports
   - Track already-exported ticket IDs

### Estimated Performance
- Basic ticket search: ~10-20 seconds per 1000 tickets
- **With full history (DEFAULT):** ~1-2 seconds per ticket (with 0.1s delay)
- **For 1000 tickets with history:** ~20-30 minutes

---

## Usage Examples

```bash
# Example 1: Export all P1 tickets from Q1 2024 (with full history by default)
export START_DATE="2024-01-01"
export END_DATE="2024-03-31"
export TICKET_PRIORITIES="P1"
python zendesk_timeframe_exporter.py

# Example 2: Export P1 and P2 tickets updated in January
export START_DATE="2024-01-01"
export END_DATE="2024-01-31"
export DATE_FIELD="updated"
export TICKET_PRIORITIES="P1,P2"
python zendesk_timeframe_exporter.py

# Example 3: Export all tickets WITHOUT full history (opt-out)
python zendesk_timeframe_exporter.py \
  --start-date 2024-03-01 \
  --end-date 2024-03-07 \
  --no-history \
  --output weekly_tickets.json

# Example 4: Export P3 and P4 tickets with full history
python zendesk_timeframe_exporter.py \
  --start-date 2024-02-01 \
  --end-date 2024-02-29 \
  --priorities P3,P4 \
  --output low_priority_feb.json
```

---

## Constants to Define

```python
# Custom field configuration
PRIORITY_FIELD_ID = 360047533253
PRIORITY_FIELD_NAME = "Ticket Priority"
VALID_PRIORITIES = ["P1", "P2", "P3", "P4"]

# Date field options
VALID_DATE_FIELDS = ["created", "updated", "solved"]
DEFAULT_DATE_FIELD = "created"

# Default behavior
DEFAULT_FETCH_FULL_HISTORY = True
```

---

## Implementation Checklist

- [ ] Create `zendesk_timeframe_exporter.py` skeleton
- [ ] Implement date validation and parsing functions
- [ ] Implement priority validation (P1-P4)
- [ ] Implement query builder with custom field syntax (field_360047533253)
- [ ] Extend `ZendeskAPIClient` with `search_tickets_by_timeframe()` method
- [ ] Implement configuration loading (env vars + CLI args)
- [ ] Implement interactive prompts for missing config
- [ ] Add enhanced progress logging
- [ ] Implement metadata in export output (include field ID)
- [ ] Add comprehensive error handling
- [ ] Create test script with P1-P4 test cases
- [ ] Write documentation (emphasize custom field usage)
- [ ] Test with real Zendesk instance (verify custom field query)
- [ ] Add usage examples with P1-P4
- [ ] Code review and optimization

---

## Key Notes

- **FETCH_FULL_HISTORY defaults to `true`** - Users must explicitly opt-out using `--no-history` flag or `FETCH_FULL_HISTORY=false`
- Custom field ID 360047533253 must be used in query syntax
- Priority values are P1, P2, P3, P4 (case-insensitive)
- Multiple priorities use OR logic in queries
