SHELL     := /bin/bash
PYTHON    ?= python3

export PYTHONWARNINGS := default

.PHONY: all test doctest lint lint-extra

all:

test: doctest lint lint-extra

doctest:
	$(PYTHON) -m doctest curl_to_requests.py

lint:
	flake8 curl_to_requests.py
	pylint curl_to_requests.py

lint-extra:
	mypy --strict --disallow-any-unimported curl_to_requests.py
