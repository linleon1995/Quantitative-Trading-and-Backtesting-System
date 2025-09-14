# Use official Python base image
FROM python:3.13-slim

# Set work directory
WORKDIR /app

# Install pip and build tools
RUN apt-get update
RUN apt-get install -y \
    build-essential \
    python3-pip

# Instal development tools
RUN apt-get install -y \
    vim

# Install uv
RUN pip install uv

COPY . .

# Now, use uv to install your project's dependencies
# The command for installing dependencies from a lock file is:
RUN uv pip install --system -r pyproject.toml

# Set default command (can be overridden in docker-compose)
CMD ["sh", "-c", "python", "src/data_source/binance_producer.py"]
