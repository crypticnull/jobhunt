PYTHON ?= python3

.PHONY: test hooks site drift lighthouse

test:
	$(PYTHON) -m unittest discover -s pipeline/tests -v

hooks:
	git config core.hooksPath .githooks

site:
	cd site && npm run build

drift:
	node tools/check_drift.mjs

lighthouse: site
	cd site && npm run lighthouse
