FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .

# ✅ Upgrade pip + build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-u", "edge_processor.py"]