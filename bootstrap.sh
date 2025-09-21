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

# Restore Postgres
if [ -f "./postgres_dump/med_parsing_dump.sql" ]; then
    echo "Restoring Postgres database..."
    PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -f ./postgres_dump/med_parsing_dump.sql
else
    echo "No Postgres dump found. Skipping restore."
fi

# Restore all MinIO buckets
if [ -d "./minio_buckets" ]; then
    echo "Restoring MinIO buckets..."
    mc alias set local http://$MINIO_HOST:$MINIO_PORT $MINIO_USER $MINIO_PASSWORD --api S3v4

    for bucket_dir in ./minio_buckets/*; do
        bucket=$(basename $bucket_dir)
        echo "Restoring bucket: $bucket"
        mc mb local/$bucket || true
        mc mirror $bucket_dir local/$bucket
    done
else
    echo "No MinIO data found. Skipping restore."
fi
