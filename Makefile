project := jaeger_client
projects := jaeger_client crossdock
flake8 := flake8
COV_DIRS := $(projects:%=--cov %)
pytest_args := -s --tb short --cov-config .coveragerc $(COV_DIRS) tests
pytest := $(clay_config) py.test $(pytest_args)
sources := $(shell find $(projects) tests -name '*.py' | grep -v version.py | grep -v thrift_gen)

test_args := --cov-report term-missing --cov-report xml --junitxml junit.xml
cover_args := --cov-report html

include crossdock/rules.mk

PY_PATH = $(PYTHONPATH):$(PWD)

.DEFAULT_GOAL := test


.PHONY: bootstrap
bootstrap:
	[ "$$VIRTUAL_ENV" != "" ]
	rm -rf *.egg-info || true
	pip install -U 'pip>=7.0,<8.0'
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	pip install -r requirements-tests.txt
	python setup.py develop

.PHONY: test
test: clean
	$(pytest) $(test_args) --benchmark-skip

.PHONY: test_ci
test_ci: clean test lint

.PHONY: test-perf
test-perf: clean
	$(pytest) $(test_args) --benchmark-only

# --benchmark-histogram --benchmark-min-time=0.001

.PHONY: cover
cover: clean
	$(pytest) $(cover_args) --benchmark-skip
	open htmlcov/index.html

.PHONY: jenkins
jenkins: bootstrap
	$(pytest) $(test_args) --benchmark-skip

.PHONY: clean
clean:
	@find $(project) "(" -name "*.pyc" -o -name "coverage.xml" -o -name "junit.xml" ")" -delete
	@find tests "(" -name "*.pyc" -o -name "coverage.xml" -o -name "junit.xml" -o -name __pycache__ ")" -delete
	@find . "(" -name "*.pyc" -o -name "coverage.xml" -o -name "junit.xml" -o -name __pycache__ ")" -delete
	@rm -rf jaeger_client.egg-info

.PHONY: lint
lint:
	$(flake8) $(projects) tests

.PHONY: shell
shell:
	ipython

# Generate jaeger thrifts
THRIFT_GEN_DIR=jaeger_client/thrift_gen
THRIFT_VER=0.9.3
THRIFT_IMG=thrift:$(THRIFT_VER)
THRIFT_PY_ARGS=new_style,tornado
THRIFT=docker run -v "${PWD}:/data" $(THRIFT_IMG) thrift

idl-submodule:
	git submodule init
	git submodule update

thrift-image:
	$(THRIFT) -version

.PHONY: thrift
thrift: idl-submodule thrift-image
	${THRIFT} -o /data --gen py:${THRIFT_PY_ARGS} -out /data/$(THRIFT_GEN_DIR) /data/idl/thrift/zipkinCore.thrift
	${THRIFT} -o /data --gen py:${THRIFT_PY_ARGS} -out /data/$(THRIFT_GEN_DIR) /data/idl/thrift/agent.thrift
	${THRIFT} -o /data --gen py:${THRIFT_PY_ARGS} -out /data/$(THRIFT_GEN_DIR) /data/idl/thrift/sampling.thrift
	rm -rf ${THRIFT_GEN_DIR}/*/*-remote

update-license:
	python scripts/updateLicense.py $(sources)	
