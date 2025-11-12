#!/bin/bash
# Script to start PostgreSQL and Redis in the sandbox
# Claude Code can run this before executing database-related tasks

set -e

echo "Configuring PostgreSQL for passwordless local access..."
# Find PostgreSQL version directory
PG_VERSION=$(ls /etc/postgresql/ 2>/dev/null | head -1)
if [ -n "$PG_VERSION" ]; then
    sudo sed -i 's/^local.*all.*postgres.*/local all postgres trust/' /etc/postgresql/$PG_VERSION/main/pg_hba.conf
    sudo sed -i 's/^local.*all.*all.*/local all all trust/' /etc/postgresql/$PG_VERSION/main/pg_hba.conf
    echo "✓ PostgreSQL configured"
else
    echo "⚠ PostgreSQL config directory not found"
fi

echo "Starting PostgreSQL..."
sudo service postgresql start

echo "Starting Redis..."
sudo service redis-server start

echo ""
echo "Services started successfully!"
echo ""
echo "PostgreSQL: listening on localhost:5432"
echo "  - Connect as: psql -U postgres"
echo "  - Create database: psql -U postgres -c 'CREATE DATABASE mydb;'"
echo ""
echo "Redis: listening on localhost:6379"
echo "  - Test connection: redis-cli ping"
