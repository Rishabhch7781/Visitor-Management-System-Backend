# 1. Base image (Konsa Python version chahiye)
FROM python:3.10-slim

# 2. Container ke andar folder banana
WORKDIR /app

# 3. requirements.txt ko container mein copy karna
COPY requirements.txt .

# 4. Saari libraries install karna
RUN pip install --no-cache-dir -r requirements.txt

# 5. Apne baaki saare code (main.py, models.py, etc.) ko copy karna
COPY . .

# 6. Container ko batana ki app kaise start karni hai
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]