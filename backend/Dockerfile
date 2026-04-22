# Backend Dockerfile — builds the C++ classifier and runs FastAPI via uvicorn.
# Build context must be the PROJECT ROOT (so we can COPY both backend/ and native/).
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends g++ make \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better layer caching)
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy source
COPY backend/ ./backend/
COPY native/  ./native/

# Compile the C++ priority engine
RUN cd native && make

# Persistent SQLite location (mount a Render disk here)
RUN mkdir -p /app/backend/data
ENV DB_PATH=/app/backend/data/complaints.db
ENV CLASSIFIER_BIN=/app/native/classifier
ENV PORT=8000

EXPOSE 8000
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
