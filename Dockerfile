# Stage 1: Build the application
FROM python:3.9-slim AS builder

WORKDIR /app

# Copy requirements.txt and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Stage 2: Create the final image
FROM python:3.9-slim

WORKDIR /app

# Copy the built application from the builder stage
COPY --from=builder /app /app

# Create a non-root user
RUN useradd -m appuser

# Change ownership of the application files to the non-root user
RUN chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

# Expose the port the application runs on
EXPOSE 5000

# Add a health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:5000/health || exit 1

# Command to run the application
CMD ["python", "agent_core.py"]
