# Gunakan image Python
FROM python:3.10-slim

# Instal FFmpeg (PENTING untuk memperbaiki error "ffmpeg was not found")
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Set direktori kerja
WORKDIR /app

# Copy file requirements dan instal library
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy semua file bot (termasuk main.py dan youtube_cookies.txt)
COPY . .

# Jalankan bot
CMD ["python", "main.py"]

