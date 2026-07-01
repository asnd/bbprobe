// Command bbprobe is a single-shot, agentless network probe. It drives the
// Prometheus blackbox_exporter probe implementations directly (no server, no
// listening port, no root) and prints a structured result to stdout, then exits.
package main

import (
	"context"
	_ "embed"
	"encoding/json"
	"flag"
	"fmt"
	"log/slog"
	"os"
	"sort"
	"strings"
	"time"

	"github.com/prometheus/blackbox_exporter/config"
)

// Injected via -ldflags "-X main.version=... -X main.commit=...".
var (
	version = "dev"
	commit  = "none"
)

//go:embed config.yml
var embeddedConfig []byte

const (
	exitSuccess   = 0 // probe(s) succeeded
	exitProbeFail = 1 // probe ran but failed
	exitUsage     = 2 // usage / config / internal error
)

func main() {
	os.Exit(run(os.Args[1:]))
}

func run(args []string) int {
	fs := flag.NewFlagSet("bbprobe", flag.ContinueOnError)
	fs.SetOutput(os.Stderr)
	fs.Usage = func() {
		fmt.Fprintf(os.Stderr, "bbprobe %s (commit %s)\n", version, commit)
		fmt.Fprintf(os.Stderr, "Usage: bbprobe --module NAME[,NAME...] --target HOST [flags]\n\n")
		fs.PrintDefaults()
	}

	var (
		moduleFlag  = fs.String("module", "", "comma-separated module name(s) from the config (e.g. http_2xx,icmp)")
		targetFlag  = fs.String("target", "", "probe target: URL, host, or IP")
		dstFlag     = fs.String("dst", "", "alias for --target (destination host/IP or FQDN)")
		configFlag  = fs.String("config", "", "path to a blackbox.yml (default: built-in embedded config)")
		timeoutFlag = fs.Duration("timeout", 10*time.Second, "per-attempt probe timeout")
		formatFlag  = fs.String("format", "json", "output format: json|prom")
		debugFlag   = fs.Bool("debug", false, "include prober debug plaintext in the result")
		repeatFlag  = fs.Int("repeat", 1, "number of attempts per module")
		versionFlag = fs.Bool("version", false, "print version/commit and exit")
	)

	if err := fs.Parse(args); err != nil {
		return exitUsage
	}
	if *versionFlag {
		fmt.Printf("bbprobe %s (commit %s)\n", version, commit)
		return exitSuccess
	}

	// --- validate flags ---
	target := *targetFlag
	if target == "" {
		target = *dstFlag
	}
	if target == "" {
		fmt.Fprintln(os.Stderr, "error: --target (or --dst) is required")
		return exitUsage
	}
	if *moduleFlag == "" {
		fmt.Fprintln(os.Stderr, "error: --module is required")
		return exitUsage
	}
	if *repeatFlag < 1 {
		fmt.Fprintln(os.Stderr, "error: --repeat must be >= 1")
		return exitUsage
	}
	if *formatFlag != "json" && *formatFlag != "prom" {
		fmt.Fprintf(os.Stderr, "error: --format must be json or prom, got %q\n", *formatFlag)
		return exitUsage
	}

	logLevel := slog.LevelInfo
	if *debugFlag {
		logLevel = slog.LevelDebug
	}
	logger := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: logLevel}))

	// --- load config ---
	cfg, err := loadConfig(*configFlag, logger)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: loading config: %v\n", err)
		return exitUsage
	}

	modules, err := resolveModules(*moduleFlag, cfg.Modules)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		return exitUsage
	}

	// --- run probes ---
	var results []probeResult
	for _, mname := range modules {
		mod := cfg.Modules[mname]
		for attempt := 1; attempt <= *repeatFlag; attempt++ {
			ctx, cancel := context.WithTimeout(context.Background(), *timeoutFlag)
			r := runProbe(ctx, target, mod, *debugFlag)
			cancel()
			if r.err != nil {
				fmt.Fprintf(os.Stderr, "error: probe %q attempt %d: %v\n", mname, attempt, r.err)
				return exitUsage
			}
			r.module = mname
			r.prober = mod.Prober
			r.attempt = attempt
			results = append(results, r)
		}
	}

	// --- emit output (stdout only) ---
	if *formatFlag == "prom" {
		if err := writeProm(os.Stdout, results); err != nil {
			fmt.Fprintf(os.Stderr, "error: writing prom output: %v\n", err)
			return exitUsage
		}
	} else {
		out := buildOutput(version+"+"+commit, target, results)
		enc := json.NewEncoder(os.Stdout)
		enc.SetIndent("", "  ")
		if err := enc.Encode(out); err != nil {
			fmt.Fprintf(os.Stderr, "error: encoding json: %v\n", err)
			return exitUsage
		}
	}

	// --- exit code: 0 only if every attempt succeeded ---
	for _, r := range results {
		if !r.success {
			return exitProbeFail
		}
	}
	return exitSuccess
}

// resolveModules splits a comma list, trims blanks, and validates each name
// exists in the config. It returns a clear error listing available modules.
func resolveModules(spec string, available map[string]config.Module) ([]string, error) {
	var names []string
	for _, part := range strings.Split(spec, ",") {
		name := strings.TrimSpace(part)
		if name == "" {
			continue
		}
		if _, ok := available[name]; !ok {
			return nil, fmt.Errorf("module %q not found in config; available: %s", name, availableModules(available))
		}
		names = append(names, name)
	}
	if len(names) == 0 {
		return nil, fmt.Errorf("no valid module names in %q", spec)
	}
	return names, nil
}

// availableModules returns a sorted, comma-joined list of configured module names.
func availableModules(available map[string]config.Module) string {
	names := make([]string, 0, len(available))
	for name := range available {
		names = append(names, name)
	}
	sort.Strings(names)
	return strings.Join(names, ", ")
}
