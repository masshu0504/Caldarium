#!/usr/bin/env bash
set -e

# Environment
POSTGRES_HOST=${POSTGRES_HOST:-ls-postgres}
POSTGRES_PORT=${POSTGRES_PORT:-5432}
POSTGRES_DB=${POSTGRES_DB:-med_parsing}
POSTGRES_USER=${POSTGRES_USER:-postgres}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-postgres}

MINIO_HOST=${MINIO_HOST:-ls-minio}
MINIO_PORT=${MINIO_PORT:-9000}
MINIO_USER=${MINIO_ROOT_USER:-minio}
MINIO_PASSWORD=${MINIO_ROOT_PASSWORD:-minio123}

# Export Postgres
mkdir -p ./postgres_dump
echo "Exporting Postgres database..."
PGPASSWORD=$POSTGRES_PASSWORD pg_dump -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB > ./postgres_dump/med_parsing_dump.sql
echo "Postgres dump saved to ./postgres_dump/med_parsing_dump.sql"

# Export all MinIO buckets
mkdir -p ./minio_buckets
echo "Exporting all MinIO buckets..."
mc alias set local http://$MINIO_HOST:$MINIO_PORT $MINIO_USER $MINIO_PASSWORD --api S3v4

buckets=$(mc ls local | awk '{print $5}')  # Get bucket names
for bucket in $buckets; do
    echo "Exporting bucket: $bucket"
    mkdir -p ./minio_buckets/$bucket
    mc mirror local/$bucket ./minio_buckets/$bucket
done

echo "All MinIO buckets exported to ./minio_buckets/"
