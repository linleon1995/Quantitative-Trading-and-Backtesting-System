# Use official Python base image
FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Install curl (required to install uv) and build dependencies
RUN apt-get update && apt-get install -y curl build-essential

# Install uv
RUN curl -Ls https://astral.sh/uv/install.sh | bash

# Add uv to PATH (default install location)
ENV PATH="/root/.local/bin:$PATH"

# Now you can use uv
RUN uv --version

# Copy project files
# COPY pyproject.toml .
COPY . .

# Now, use uv to install your project's dependencies
# The command for installing dependencies from a lock file is:
RUN uv pip install --system pyproject.toml



# Set default command (can be overridden in docker-compose)
CMD ["python", "data_source/binance_producer.py"]
