FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt recognition_service/requirements.txt
RUN pip install --no-cache-dir -r recognition_service/requirements.txt
COPY . .
ENV PYTHONPATH=/app
EXPOSE 8090
CMD ["flask", "--app", "recognition_service.app", "run", "--host=0.0.0.0", "--port=8090"]
