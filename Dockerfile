FROM python:3.12-alpine

WORKDIR /app

RUN apk add --no-cache ffmpeg

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

RUN mkdir -p /app/data

ENV FLASK_ENV=production

EXPOSE 5000

CMD ["python", "app.py"]
