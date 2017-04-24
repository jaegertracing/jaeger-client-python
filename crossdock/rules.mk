XDOCK_YAML=crossdock/docker-compose.yml
TRACETEST_THRIFT=idl/thrift/crossdock/tracetest.thrift

.PHONY: clean-compile
clean-compile:
	find . -name '*.pyc' -exec rm {} \;

${TRACETEST_THRIFT}:
	git submodule update --init idl

.PHONY: docker
docker: clean-compile
	docker build -f crossdock/Dockerfile -t jaeger-client-python .

.PHONY: crossdock
crossdock: ${TRACETEST_THRIFT}
	docker-compose -f $(XDOCK_YAML) kill python
	docker-compose -f $(XDOCK_YAML) rm -f python
	docker-compose -f $(XDOCK_YAML) build python
	docker-compose -f $(XDOCK_YAML) run crossdock

.PHONY: crossdock-fresh
crossdock-fresh: ${TRACETEST_THRIFT}
	docker-compose -f $(XDOCK_YAML) kill
	docker-compose -f $(XDOCK_YAML) rm --force
	docker-compose -f $(XDOCK_YAML) pull
	docker-compose -f $(XDOCK_YAML) build
	docker-compose -f $(XDOCK_YAML) run crossdock

.PHONY: crossdock-logs
crossdock-logs:
	docker-compose -f $(XDOCK_YAML) logs

.PHONY: install_docker_ci
install_docker_ci:
	@echo "Installing docker-compose $${DOCKER_COMPOSE_VERSION:?'DOCKER_COMPOSE_VERSION env not set'}"
	sudo rm -f /usr/local/bin/docker-compose
	curl -L https://github.com/docker/compose/releases/download/$${DOCKER_COMPOSE_VERSION}/docker-compose-`uname -s`-`uname -m` > docker-compose
	chmod +x docker-compose
	sudo mv docker-compose /usr/local/bin
	docker-compose version
