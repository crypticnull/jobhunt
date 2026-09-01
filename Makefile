PYTHON ?= python3

.PHONY: test validate hooks site drift lighthouse

test:
	$(PYTHON) -m unittest discover -s pipeline/tests -t . -v
	$(PYTHON) -m unittest discover -s scraper/tests -t . -v

validate:
	$(PYTHON) -m pipeline.validate

hooks:
	git config core.hooksPath .githooks

site:
	cd site && npm run build

drift:
	node tools/check_drift.mjs

lighthouse: site
	cd site && npm run lighthouse
