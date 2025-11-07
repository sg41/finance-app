all: run

tests: test

test:
	docker run --network=host -v /home/serge/s21/finance_app/test:/etc/newman -t postman/newman run postman_collection.json -e postman_environment.json --insecure
	
run:
	uvicorn main:app --reload --host 0.0.0.0 --port 8001 --log-level info || echo " Try to run: source .venv/bin/activate"
	
.PHONY: test
