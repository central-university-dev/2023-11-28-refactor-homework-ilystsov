CODE_FOLDER := refactoring_tool
TEST_FOLDER := tests
.PHONY: install format lint test

install:
	poetry install

format:
	poetry run black --line-length 120 $(CODE_FOLDER)

lint:
	poetry run flake8 $(CODE_FOLDER)

test:
	poetry run pytest


