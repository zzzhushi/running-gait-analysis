.PHONY: web-static serve-static test test-web

# Bundle the engine into web/py/gaitlab.zip so the static build matches production.
web-static:
	python3 scripts/build_web.py
	touch web/.nojekyll

# Serve the static build locally exactly as GitHub Pages would (default runtime=static).
serve-static: web-static
	cd web && python3 -m http.server 8000

# Python engine suite — the numeric source of truth.
test:
	pytest

# JS/parity suite (mapping unit + Pyodide==Python parity). Needs `npm ci` first.
test-web: web-static
	npm test
