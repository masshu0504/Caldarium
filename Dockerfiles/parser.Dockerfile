# Use an official Python image as a base
FROM python:3.11-slim-buster

# Set environment variables to ensure the application logs appear immediately
ENV PYTHONUNBUFFERED 1
ENV APP_HOME /app
WORKDIR $APP_HOME

# --- START FIX: APT 404 NOT FOUND ERROR ---
# Temporarily switch the Debian repository URL to the archive site 
# to allow old package lists to update and resolve the 404 error.
RUN sed -i 's/http:\/\/deb.debian.org/http:\/\/archive.debian.org/g' /etc/apt/sources.list && \
    sed -i 's/http:\/\/security.debian.org/http:\/\/archive.debian.org\/debian-security/g' /etc/apt/sources.list
# --- END FIX ---

# 1. Update package list in a separate layer
# This RUN command should now succeed using the archive sources.
RUN apt-get update

# 2. Install system dependencies needed for python packages, and clean up.
RUN apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt $APP_HOME/

# Install Python dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . $APP_HOME/

# Command to run the FastAPI application using Uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
