FROM python:3.12-slim

WORKDIR /app

COPY . /app

RUN pip install tensorflow pillow

CMD ["python", "service.py"]
