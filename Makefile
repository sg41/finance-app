all: run

tests: test

test:
	docker run --network=host -v $(shell pwd)/test:/etc/newman -t postman/newman run postman_collection.json -e postman_environment.json --insecure
	
run:
	cd backend; uvicorn main:app --reload --host 0.0.0.0 --port 8001 --log-level info || echo " Try to run: source .venv/bin/activate"

database:
# 	docker compose up -d
	cd backend; python3 create_test_user.py
 
.PHONY: test
