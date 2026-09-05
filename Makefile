PYTHON ?= python3

.PHONY: test validate lint demo hooks site drift lighthouse

test:
	$(PYTHON) -m unittest discover -s pipeline/tests -t . -v
	$(PYTHON) -m unittest discover -s scraper/tests -t . -v
	$(PYTHON) -m unittest discover -s letters/tests -t . -v

validate:
	$(PYTHON) -m pipeline.validate

lint:
	$(PYTHON) -m letters.voicelint --profile repo
	$(PYTHON) -m letters.voicelint --profile letter

demo:
	$(PYTHON) tools/demo.py

hooks:
	git config core.hooksPath .githooks

site:
	cd site && npm run build

drift:
	node tools/check_drift.mjs
	node tools/check_tokens.mjs

lighthouse: site
	cd site && npm run lighthouse
