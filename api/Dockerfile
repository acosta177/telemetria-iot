FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY api/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY shared /srv/shared
COPY api /srv/api
RUN useradd --create-home appuser
USER appuser
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
