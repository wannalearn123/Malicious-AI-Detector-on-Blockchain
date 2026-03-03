FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Initialize database
RUN python -c "from src.data.models import init_database; import os; init_database(os.getenv('DATABASE_URL', 'sqlite:///tmp.db'))"

EXPOSE 8000 9090

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]