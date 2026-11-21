FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY processor/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY shared /srv/shared
COPY processor /srv/processor
RUN useradd --create-home appuser
USER appuser
EXPOSE 8001
CMD ["uvicorn", "processor.main:app", "--host", "0.0.0.0", "--port", "8001"]
