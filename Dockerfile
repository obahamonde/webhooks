FROM python:3.9.7-slim-buster

WORKDIR /app

COPY . .

RUN pip install -r requirements.txt

CMD ["adev", "runserver", "--livereload", "--host", "0.0.0.0", "--port", "8080"]