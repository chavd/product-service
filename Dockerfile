FROM python:3.13-slim

# Do not write .pyc files, and stream stdout/stderr straight to the logs
# instead of buffering it — otherwise container output arrives in chunks.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies are copied and installed before the source, so that editing
# code does not invalidate the cached pip layer.
COPY requirements.txt requirements-dev.txt ./
# This image is the development and test environment, so it installs the
# tooling as well. A production build would use requirements.txt only.
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .

# Run as a non-root user.
RUN useradd --create-home --uid 1000 app && chown -R app:app /app
USER app

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
