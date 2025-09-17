install:
	pipenv lock && pipenv sync

installdev:
	pipenv lock && pipenv sync --dev

build:
	docker build -t catering-api .

clean:
	docker image prune


run:
	python3 manage.py runserver

docker:
	docker compose up -d

dockerdown:
	docker compose down


silpo_mock:
	python3 -m uvicorn tests.providers.silpo:app --port 8001 --reload

kfc_mock:
	python3 -m uvicorn tests.providers.kfc:app --port 8002 --reload

uklon_mock:
	python3 -m uvicorn tests.providers.uklon:app --port 8003 --reload


worker_default:
	celery -A cateringproject worker -l INFO -Q default

worker_high:
	celery -A cateringproject worker -l INFO -Q high_priority

worker_low:
	celery -A cateringproject worker -l INFO -Q low_priority