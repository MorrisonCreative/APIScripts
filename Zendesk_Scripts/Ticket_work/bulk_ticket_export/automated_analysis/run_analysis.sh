#!/bin/bash
# Quick test script - runs analysis without sending email
# Usage: ./run_analysis.sh [claude|gemini] [P1|P1,P2|etc]

set -e  # Exit on error

# Auto-detect script directory (works on any machine)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load environment variables from shell config
if [ -f ~/.zshrc ]; then
    source ~/.zshrc
fi

# Default to Claude if no argument provided
LLM_CHOICE="${1:-claude}"
PRIORITIES="${2:-}"

if [ "$LLM_CHOICE" != "claude" ] && [ "$LLM_CHOICE" != "gemini" ]; then
    echo "Usage: $0 [claude|gemini] [priorities]"
    echo "Example: $0 claude P1"
    echo "Example: $0 gemini P1,P2"
    echo "Default: claude, all priorities"
    exit 1
fi

echo "Running ticket analysis with $LLM_CHOICE (DRY RUN mode)..."
if [ -n "$PRIORITIES" ]; then
    echo "Filtering for priorities: $PRIORITIES"
fi
echo "============================================"

# Build command with optional priorities filter
CMD="python3 ticket_analyzer.py --llm $LLM_CHOICE --dry-run"
if [ -n "$PRIORITIES" ]; then
    CMD="$CMD --priorities $PRIORITIES"
fi

# Run with dry-run flag to preview without sending email
eval $CMD

echo ""
echo "============================================"
echo "Dry run completed! No email was sent."
echo ""
echo "To send actual email, run:"
if [ -n "$PRIORITIES" ]; then
    echo "  python3 ticket_analyzer.py --llm $LLM_CHOICE --priorities $PRIORITIES"
else
    echo "  python3 ticket_analyzer.py --llm $LLM_CHOICE"
fi
