#!/bin/sh
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f /tmp/initialize_database.sql

# Check if the TEST_DATA environment variable is set to True
if [ "$TEST_DATA" = 1 ]; then
  # Loop through all .sql files in the /tmp/test_data_database directory
  for sql_file in /tmp/test_data_database/*.sql;
  do
    # Execute each SQL file
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f "$sql_file"
  done
fi
