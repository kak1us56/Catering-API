FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update -y \
    && apt-get install -y build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --upgrade pip setuptools pipenv

COPY Pipfile Pipfile.lock ./
RUN pipenv install --system --deploy

COPY . .

FROM base AS dev

ENV C_FORCE_ROOT="true"
ENV DJANGO_DEBUG=1

RUN pipenv sync --dev --system

EXPOSE 8000/tcp
ENTRYPOINT [ "python" ]
CMD [ "manage.py", "runserver", "0.0.0.0:8000" ]



FROM base AS prod

ENV DJANGO_DEBUG=
ENV GUNICORN_CMD_ARGS="--bind 0.0.0.0:8000 --reload"

RUN pipenv install --deploy --system

EXPOSE 8000/tcp
ENTRYPOINT [ "python" ]
CMD [ "-m", "gunicorn", "config.wsgi:application"]