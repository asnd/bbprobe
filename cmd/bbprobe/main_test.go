package main

import (
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

// TestHTTP2xxSuccess spins up a local HTTP server and runs the embedded
// http_2xx module against it, asserting success, JSON shape, and that the
// probe_http_duration_seconds phases are present.
func TestHTTP2xxSuccess(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok"))
	}))
	defer srv.Close()

	logger := slog.New(slog.NewTextHandler(nopWriter{}, nil))
	cfg, err := loadConfig("", logger)
	if err != nil {
		t.Fatalf("loadConfig: %v", err)
	}
	mod, ok := cfg.Modules["http_2xx"]
	if !ok {
		t.Fatal("embedded config missing http_2xx module")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	r := runProbe(ctx, srv.URL, mod, false)
	if r.err != nil {
		t.Fatalf("runProbe error: %v", r.err)
	}
	r.module, r.prober, r.attempt = "http_2xx", mod.Prober, 1

	if !r.success {
		t.Fatalf("expected probe success, got failure")
	}

	// JSON must marshal and round-trip.
	out := buildOutput("test+none", srv.URL, []probeResult{r})
	raw, err := json.Marshal(out)
	if err != nil {
		t.Fatalf("json.Marshal: %v", err)
	}
	var parsed output
	if err := json.Unmarshal(raw, &parsed); err != nil {
		t.Fatalf("json.Unmarshal: %v", err)
	}

	if parsed.Summary.ProbeSuccess != 1 {
		t.Errorf("summary.probe_success = %d, want 1", parsed.Summary.ProbeSuccess)
	}
	if len(parsed.Results) != 1 {
		t.Fatalf("expected 1 result, got %d", len(parsed.Results))
	}

	// probe_http_duration_seconds phases must be present.
	phases := map[string]bool{}
	sawProbeSuccess := false
	for _, s := range parsed.Results[0].Metrics {
		switch s.Name {
		case "probe_http_duration_seconds":
			if ph := s.Labels["phase"]; ph != "" {
				phases[ph] = true
			}
		case "probe_success":
			if s.Value == 1 {
				sawProbeSuccess = true
			}
		}
	}
	if !sawProbeSuccess {
		t.Error("probe_success metric with value 1 not found")
	}
	if len(phases) == 0 {
		t.Error("no probe_http_duration_seconds phases found")
	}
	for _, want := range []string{"connect", "processing", "resolve", "transfer"} {
		if !phases[want] {
			t.Errorf("missing probe_http_duration_seconds phase %q", want)
		}
	}
}

type nopWriter struct{}

func (nopWriter) Write(p []byte) (int, error) { return len(p), nil }
