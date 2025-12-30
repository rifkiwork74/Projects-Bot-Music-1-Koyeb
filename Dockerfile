# Menggunakan image Node.js sebagai dasar
FROM node:18-bullseye

# Langkah krusial: Menginstal FFmpeg di sistem hosting Koyeb
RUN apt-get update && apt-get install -y ffmpeg

# Menentukan direktori kerja di dalam server
WORKDIR /app

# Menyalin file package bot dan menginstal dependensi
COPY package*.json ./
RUN npm install

# Menyalin seluruh kode bot ke dalam server
COPY . .

# Perintah untuk menjalankan bot Anda
CMD ["node", "index.js"]
