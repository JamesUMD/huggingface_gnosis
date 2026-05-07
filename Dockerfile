# Reflex on Hugging Face Spaces (Docker SDK).
# Runs both frontend and backend on the single port HF exposes (7860).
FROM python:3.13-slim

# System deps Reflex needs at runtime: curl + unzip for bun, build-essential for
# any wheels that need compiling, ca-certificates for HTTPS calls (Anthropic).
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl unzip ca-certificates build-essential \
    && rm -rf /var/lib/apt/lists/*

# HF Spaces runs containers as a non-root user with UID 1000.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    REFLEX_DIR=/home/user/.reflex

WORKDIR /home/user/app

# Install Python deps first so Docker can cache this layer.
COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir --user --upgrade pip \
    && pip install --no-cache-dir --user -r requirements.txt

# Copy the app source.
COPY --chown=user:user . .

# Initialize Reflex (downloads bun + installs Node deps into .web/).
# Done at build time so the cold start serves traffic immediately.
RUN reflex init --template blank --loglevel info

EXPOSE 7860

# `--single-port` makes Reflex 0.9+ serve both frontend and backend on one
# port — perfect for HF Spaces which only exposes one.
CMD ["reflex", "run", \
     "--env=prod", \
     "--single-port", \
     "--backend-host=0.0.0.0", \
     "--backend-port=7860", \
     "--loglevel=info"]
