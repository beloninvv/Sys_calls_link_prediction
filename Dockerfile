FROM python:3.10-slim

WORKDIR /app

# Установка PyTorch для CPU (совместим с ARM64)
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# Копирование вашего кода
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["python", "your_script.py"]