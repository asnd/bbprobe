package main

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
	"time"

	"github.com/prometheus/blackbox_exporter/config"
	"github.com/prometheus/blackbox_exporter/prober"
	"github.com/prometheus/client_golang/prometheus"
	dto "github.com/prometheus/client_model/go"
)

// probeResult is the raw outcome of a single probe attempt.
type probeResult struct {
	module   string
	prober   string
	attempt  int
	success  bool
	duration float64
	families []*dto.MetricFamily
	debug    string
	err      error
}

// loadConfig loads a blackbox configuration. When path is empty the embedded
// default config is written to a temp file and loaded, so we reuse the exact
// upstream parsing, default-application and validation logic (config.SafeConfig).
func loadConfig(path string, logger *slog.Logger) (*config.Config, error) {
	if path == "" {
		tmp, err := os.CreateTemp("", "bbprobe-*.yml")
		if err != nil {
			return nil, fmt.Errorf("creating temp config: %w", err)
		}
		defer os.Remove(tmp.Name())
		if _, err := tmp.Write(embeddedConfig); err != nil {
			tmp.Close()
			return nil, fmt.Errorf("writing temp config: %w", err)
		}
		if err := tmp.Close(); err != nil {
			return nil, fmt.Errorf("closing temp config: %w", err)
		}
		path = tmp.Name()
	}

	// A throwaway registry satisfies NewSafeConfig's internal reload gauges.
	sc := config.NewSafeConfig(prometheus.NewRegistry())
	if err := sc.ReloadConfig(path, logger); err != nil {
		return nil, err
	}
	return sc.C, nil
}

// runProbe mirrors what prober.Handler does (minus the HTTP layer): it builds a
// registry, registers the standard probe_success / probe_duration_seconds
// gauges, invokes the module's ProbeFn, and gathers the resulting metrics.
func runProbe(ctx context.Context, target string, module config.Module, debug bool) probeResult {
	fn, ok := prober.Probers[module.Prober]
	if !ok {
		return probeResult{err: fmt.Errorf("no prober registered for %q", module.Prober)}
	}

	reg := prometheus.NewRegistry()
	probeSuccessGauge := prometheus.NewGauge(prometheus.GaugeOpts{
		Name: "probe_success",
		Help: "Displays whether or not the probe was a success",
	})
	probeDurationGauge := prometheus.NewGauge(prometheus.GaugeOpts{
		Name: "probe_duration_seconds",
		Help: "Returns how long the probe took to complete in seconds",
	})
	if err := reg.Register(probeSuccessGauge); err != nil {
		return probeResult{err: fmt.Errorf("registering probe_success: %w", err)}
	}
	if err := reg.Register(probeDurationGauge); err != nil {
		return probeResult{err: fmt.Errorf("registering probe_duration_seconds: %w", err)}
	}

	// Probe logs are captured in logBuf (surfaced via --debug) and, at the
	// appropriate level, echoed to stderr so stdout stays clean.
	var logBuf bytes.Buffer
	level := slog.LevelInfo
	if debug {
		level = slog.LevelDebug
	}
	w := io.MultiWriter(os.Stderr, &logBuf)
	logger := slog.New(slog.NewTextHandler(w, &slog.HandlerOptions{Level: level}))

	start := time.Now()
	success := fn(ctx, target, module, reg, logger)
	dur := time.Since(start).Seconds()

	probeDurationGauge.Set(dur)
	if success {
		probeSuccessGauge.Set(1)
	}

	mfs, err := reg.Gather()
	if err != nil {
		return probeResult{err: fmt.Errorf("gathering metrics: %w", err)}
	}

	res := probeResult{success: success, duration: dur, families: mfs}
	if debug {
		res.debug = prober.DebugOutput(&module, &logBuf, reg)
	}
	return res
}
