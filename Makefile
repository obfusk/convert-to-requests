SHELL   := /bin/bash
PYTHON  ?= python3

export PYTHONWARNINGS := default

.PHONY: all install test doctest lint lint-extra clean cleanup

all:

install:
	$(PYTHON) -mpip install -e .

test: doctest lint lint-extra

doctest:
	$(PYTHON) -m doctest to_requests/__init__.py

lint:
	flake8 to_requests/__init__.py
	pylint to_requests/__init__.py

lint-extra:
	mypy --strict --disallow-any-unimported to_requests/__init__.py

clean: cleanup
	rm -fr to_requests.egg-info/

cleanup:
	find -name '*~' -delete -print
	rm -fr __pycache__/ .mypy_cache/
	rm -fr build/ dist/
	rm -fr .coverage htmlcov/

.PHONY: _package _publish

_package:
	SOURCE_DATE_EPOCH="$$( git log -1 --pretty=%ct )" \
	  $(PYTHON) setup.py sdist bdist_wheel
	twine check dist/*

_publish: cleanup _package
	read -r -p "Are you sure? "; \
	[[ "$$REPLY" == [Yy]* ]] && twine upload dist/*
