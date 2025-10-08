# Base image: Use a slightly older but stable Debian slim image to ensure compatibility with many Python packages.
FROM python:3.11-slim-buster

# Set environment variables to ensure the application logs appear immediately
ENV PYTHONUNBUFFERED 1
ENV APP_HOME /app
WORKDIR $APP_HOME

# --- System Dependency Fixes and Compiler Tools ---
# 1. Fix old Debian buster repository URLs (solves 404/exit code 100 errors)
RUN sed -i 's/http:\/\/deb.debian.org/http:\/\/archive.debian.org/g' /etc/apt/sources.list && \
    sed -i 's/http:\/\/security.debian.org/http:\/\/archive.debian.org/g' /etc/apt/sources.list

# 2. Update and install necessary compiler tools and postgres development headers
#    This is required to successfully install packages like psycopg2-binary and pdfplumber.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    # Clean up apt caches to minimize image size
    && rm -rf /var/lib/apt/lists/*
# --- End System Dependency Fixes ---

# Copy the requirements file into the container
COPY requirements.txt $APP_HOME/

# Install Python dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code (app.py, parser_prototype.py, etc.)
COPY . $APP_HOME/

EXPOSE 8000

# Command to run the FastAPI application using Uvicorn
# The command starts the server permanently.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
