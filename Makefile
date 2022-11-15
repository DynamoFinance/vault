init:
	pip install -r requirements.txt
	npm ci
	ape plugins install .
