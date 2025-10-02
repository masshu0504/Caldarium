FROM python:3.11-slim

# Install wait-on tools if needed (e.g., netcat or curl, although sleep is simpler)
# We will rely on simple sleep for this example, which is already available in the slim image.

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

EXPOSE 8000

# Use /bin/sh -c to run multiple commands:
# 1. Print a message.
# 2. Wait for 5 seconds to allow the ls-postgres service to fully initialize.
# 3. Start the uvicorn server.
# NOTE: Using 'sh -c' requires wrapping the command in a string.
CMD ["/bin/sh", "-c", "echo 'Waiting 5 seconds for ls-postgres to start...' && sleep 5 && uvicorn main:app --host 0.0.0.0 --port 8000"]


