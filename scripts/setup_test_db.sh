#!/bin/bash
# Script to set up the test database for cloud-agent
# This is useful when running tests in sandboxes or fresh environments

set -e

DB_NAME="cloudagent"
DB_USER="postgres"

echo "Setting up test database..."

# Drop database if it exists (to reset)
psql -U $DB_USER -c "DROP DATABASE IF EXISTS $DB_NAME;" 2>/dev/null || true

# Create fresh database
psql -U $DB_USER -c "CREATE DATABASE $DB_NAME;"

echo "✓ Database '$DB_NAME' created successfully"
echo ""
echo "Next steps:"
echo "  1. Run migrations: uv run alembic upgrade head"
echo "  2. Run tests: uv run pytest tests/ -v --cov=app --cov-report=term-missing"
