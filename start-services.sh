#!/bin/bash
# Script to start PostgreSQL and Redis in the sandbox
# Claude Code can run this before executing database-related tasks

set -e

echo "Configuring PostgreSQL for passwordless local access..."
# Find PostgreSQL version directory
PG_VERSION=$(ls /etc/postgresql/ 2>/dev/null | head -1)
if [ -n "$PG_VERSION" ]; then
    # Configure both Unix socket (local) and TCP (host) connections for trust auth
    sudo sed -i 's/^local.*all.*postgres.*/local all postgres trust/' /etc/postgresql/$PG_VERSION/main/pg_hba.conf
    sudo sed -i 's/^local.*all.*all.*/local all all trust/' /etc/postgresql/$PG_VERSION/main/pg_hba.conf
    # Add host-based auth for localhost connections
    echo "host all all 127.0.0.1/32 trust" | sudo tee -a /etc/postgresql/$PG_VERSION/main/pg_hba.conf > /dev/null
    echo "host all all ::1/128 trust" | sudo tee -a /etc/postgresql/$PG_VERSION/main/pg_hba.conf > /dev/null
    echo "✓ PostgreSQL configured"
else
    echo "⚠ PostgreSQL config directory not found"
fi

echo "Starting PostgreSQL..."
sudo service postgresql start

echo "Reloading PostgreSQL configuration..."
sudo service postgresql reload

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
