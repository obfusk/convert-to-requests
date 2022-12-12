SHELL     := /bin/bash
PYTHON    ?= python3

export PYTHONWARNINGS := default

.PHONY: all test doctest lint lint-extra

all:

test: doctest lint lint-extra

doctest:
	$(PYTHON) -m doctest to_requests.py

lint:
	flake8 to_requests.py
	pylint to_requests.py

lint-extra:
	mypy --strict --disallow-any-unimported to_requests.py
