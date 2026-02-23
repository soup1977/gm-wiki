FROM python:3.11-slim

WORKDIR /app

# Copy and install dependencies first — this layer is cached unless requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create upload directory (images/maps uploaded by the GM)
RUN mkdir -p /app/app/static/uploads

# Expose the port gunicorn will listen on
EXPOSE 5001

# Entrypoint runs migrations first, then starts the server
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh
CMD ["/app/docker-entrypoint.sh"]
