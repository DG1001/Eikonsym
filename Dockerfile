# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Prevent python from writing pyc files to disc
ENV PYTHONDONTWRITEBYTECODE 1
# Ensure python output is sent straight to terminal (useful for logs)
ENV PYTHONUNBUFFERED 1

# Install system dependencies if needed (e.g., for Pillow or other C extensions)
# RUN apt-get update && apt-get install -y --no-install-recommends some-package && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Create a non-root user and group
RUN addgroup --system nonroot && adduser --system --ingroup nonroot nonroot
# Ensure the non-root user owns the app directory and potentially persistent data directories
# Adjust paths if your database/uploads are outside /app
RUN mkdir -p /app/static/uploads && chown -R nonroot:nonroot /app
USER nonroot

# Expose the port the app runs on
EXPOSE 5000

# Define the command to run the application using Gunicorn
# Adjust the number of workers (-w) based on your server resources
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
