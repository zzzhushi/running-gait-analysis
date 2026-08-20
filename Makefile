.PHONY: web-static serve-static test test-web check-env test-all

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

# Which test layers can this machine actually run? CI runs three; a box missing one
# (typically node) runs the rest and looks green while a regression ships.
check-env:
	python3 scripts/check_env.py

# Everything CI runs. Fails fast if a required layer can't run locally, rather than
# quietly skipping it.
test-all:
	python3 scripts/check_env.py --strict
	pytest
	npm test
