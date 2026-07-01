BINARY  := bbprobe
PKG     := ./cmd/bbprobe
DIST    := dist

VERSION ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo dev)
COMMIT  ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo none)
LDFLAGS := -s -w -X main.version=$(VERSION) -X main.commit=$(COMMIT)

GO      ?= go
BUILD   := CGO_ENABLED=0 $(GO) build -trimpath -ldflags "$(LDFLAGS)"

.PHONY: all build cross linux-amd64 linux-arm64 darwin-arm64 test vet tidy clean

all: build

## build: native static binary in the current directory
build:
	$(BUILD) -o $(BINARY) $(PKG)

## cross: build all release targets into $(DIST)/
cross: linux-amd64 linux-arm64 darwin-arm64

linux-amd64:
	@mkdir -p $(DIST)
	GOOS=linux GOARCH=amd64 $(BUILD) -o $(DIST)/$(BINARY)-linux-amd64 $(PKG)

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
