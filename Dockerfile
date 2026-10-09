FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DB_PATH=/data/user_data.db

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as uid 1000 so files in the bind-mounted ./data directory are owned by
# the default login user on most Linux servers (ubuntu / opc).
RUN useradd --uid 1000 --create-home app && mkdir -p /data && chown app:app /data
USER app

CMD ["python", "bot.py"]
