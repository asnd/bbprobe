BINARY  := bbprobe
PKG     := ./cmd/bbprobe
DIST    := dist

VERSION ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo dev)
COMMIT  ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo none)
LDFLAGS := -s -w -X main.version=$(VERSION) -X main.commit=$(COMMIT)

GO      ?= go
BUILD   := CGO_ENABLED=0 $(GO) build -trimpath -ldflags "$(LDFLAGS)"

NSX_PKG ?= python/nsx-robotframework
NSX_PY  ?= python3

.PHONY: all build cross linux-amd64 linux-386 linux-arm64 darwin-arm64 test vet tidy clean
.PHONY: nsxlib-build nsxlib-test nsxlib-lint nsxlib-publish nsxlib-clean

all: build

## build: native static binary in the current directory
build:
	$(BUILD) -o $(BINARY) $(PKG)

## cross: build all release targets into $(DIST)/
cross: linux-amd64 linux-386 linux-arm64 darwin-arm64

linux-amd64:
	@mkdir -p $(DIST)
	GOOS=linux GOARCH=amd64 $(BUILD) -o $(DIST)/$(BINARY)-linux-amd64 $(PKG)

linux-386:
	@mkdir -p $(DIST)
	GOOS=linux GOARCH=386 $(BUILD) -o $(DIST)/$(BINARY)-linux-386 $(PKG)

linux-arm64:
	@mkdir -p $(DIST)
	GOOS=linux GOARCH=arm64 $(BUILD) -o $(DIST)/$(BINARY)-linux-arm64 $(PKG)

darwin-arm64:
	@mkdir -p $(DIST)
	GOOS=darwin GOARCH=arm64 $(BUILD) -o $(DIST)/$(BINARY)-darwin-arm64 $(PKG)

## test: run unit tests
test:
	$(GO) test ./...

## vet: run go vet
vet:
	$(GO) vet ./...

## tidy: resolve and pin dependencies
tidy:
	$(GO) mod tidy

## clean: remove build artifacts
clean:
	rm -f $(BINARY)
	rm -rf $(DIST)

## nsxlib-build: build the nsx-robotframework sdist + wheel
nsxlib-build:
	cd $(NSX_PKG) && $(NSX_PY) -m pip install --quiet build && $(NSX_PY) -m build

## nsxlib-test: run the nsx-robotframework unit + robot suites
nsxlib-test:
	cd $(NSX_PKG) && $(NSX_PY) -m pytest -q tests
	cd $(NSX_PKG) && $(NSX_PY) -m robot --pythonpath tests/robot/lib --outputdir build/robot-results --consolecolors off tests/robot

## nsxlib-lint: lint the nsx-robotframework package (ruff)
nsxlib-lint:
	cd $(NSX_PKG) && $(NSX_PY) -m ruff check src tests

## nsxlib-publish: build and upload the nsx-robotframework package to PyPI (manual)
nsxlib-publish:
	cd $(NSX_PKG) && $(NSX_PY) -m pip install --quiet build twine && $(NSX_PY) -m build && $(NSX_PY) -m twine upload dist/*

## nsxlib-clean: remove python build/test artifacts
nsxlib-clean:
	rm -rf $(NSX_PKG)/build $(NSX_PKG)/dist $(NSX_PKG)/src/nsx_robotframework.egg-info $(NSX_PKG)/src/NSXLibrary.egg-info
	find $(NSX_PKG) -type d -name __pycache__ -prune -exec rm -rf {} +
