FROM postgres:14

# Install necessary packages and PostGIS extension
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-14-postgis-3 \
        postgresql-14-postgis-3-scripts \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy test_data_database
COPY test_data_database /tmp/test_data_database

# Copy initialise_database.sql
COPY initialize_database.sql /tmp/initialize_database.sql

# Copy in the initialise_postgresql.sh script
COPY /initialize_database.sh /docker-entrypoint-initdb.d/
