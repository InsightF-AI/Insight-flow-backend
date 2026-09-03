FROM python:3.12-slim

WORKDIR /app

COPY . .

# Imagem da demo: API minima (app.main). Nao instala o stack completo do backend.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir fastapi uvicorn

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
