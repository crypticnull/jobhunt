PYTHON ?= python3

.PHONY: test hooks

test:
	$(PYTHON) -m unittest discover -s pipeline/tests -v

hooks:
	git config core.hooksPath .githooks
