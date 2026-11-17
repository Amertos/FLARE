# FLARE — convenience targets. Everything here is also a plain documented command
# in README.md, so the project does not depend on `make` being installed.
.PHONY: install test log api web build verify memo demo deploy

install:            ## install backend + frontend dependencies
	py -m pip install -r backend/requirements.txt
	cd frontend && npm ci

test:               ## engine + API + router + memo tests
	py -m pytest backend/tests -q

log:                ## regenerate the dossier §6 published test log (fails on drift)
	py -m backend.tools.reproduce_dossier_log

build:              ## type-check, lint and build the frontend
	cd frontend && npm run lint && npm run build

verify: test log build  ## everything CI runs

api:                ## run the API on :8787
	py -m uvicorn backend.app.main:app --port 8787

web:                ## run the UI dev server on :5173
	cd frontend && npm run dev

demo:               ## build the UI, then serve API + UI together on :8000
	cd frontend && npm ci && npm run build
	py -m uvicorn backend.app.main:app --port 8000

memo:               ## write the decision memo for the Exploration Atmosphere
	curl -s "http://127.0.0.1:8787/api/report?pressure_psia=8.2&o2_pct=34&gravity=microgravity&material_class=polymer&download=true" -o flare-memo.md
	@echo "wrote flare-memo.md"

deploy:             ## deploy to Vercel production (VERCEL_TOKEN=... make deploy)
	vercel --prod --yes --token "$(VERCEL_TOKEN)"
