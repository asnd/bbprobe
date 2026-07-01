package main

import (
	"io"

	dto "github.com/prometheus/client_model/go"
	"github.com/prometheus/common/expfmt"
)

// sample is one gathered metric sample flattened for JSON.
type sample struct {
	Name   string            `json:"name"`
	Labels map[string]string `json:"labels,omitempty"`
	Value  float64           `json:"value"`
}

type resultJSON struct {
	Module   string   `json:"module"`
	Prober   string   `json:"prober"`
	Attempt  int      `json:"attempt"`
	Success  bool     `json:"success"`
	Duration float64  `json:"duration_seconds"`
	Metrics  []sample `json:"metrics"`
	Debug    string   `json:"debug,omitempty"`
}

type latency struct {
	Min float64 `json:"min"`
	Avg float64 `json:"avg"`
	Max float64 `json:"max"`
}

type summary struct {
	ProbeSuccess int     `json:"probe_success"`
	Total        int     `json:"total"`
	Succeeded    int     `json:"succeeded"`
	Failed       int     `json:"failed"`
	Latency      latency `json:"latency_seconds"`
}

type output struct {
	Version string       `json:"version"`
	Target  string       `json:"target"`
	Results []resultJSON `json:"results"`
	Summary summary      `json:"summary"`
}

// familiesToSamples flattens gathered metric families into JSON samples.
func familiesToSamples(mfs []*dto.MetricFamily) []sample {
	out := make([]sample, 0, len(mfs))
	for _, mf := range mfs {
		name := mf.GetName()
		for _, m := range mf.GetMetric() {
			var val float64
			switch mf.GetType() {
			case dto.MetricType_GAUGE:
				val = m.GetGauge().GetValue()
			case dto.MetricType_COUNTER:
				val = m.GetCounter().GetValue()
			case dto.MetricType_UNTYPED:
				val = m.GetUntyped().GetValue()
			default:
				// Skip histograms/summaries: blackbox probe metrics are gauges/counters.
				continue
			}
			s := sample{Name: name, Value: val}
			if lbls := m.GetLabel(); len(lbls) > 0 {
				s.Labels = make(map[string]string, len(lbls))
				for _, lp := range lbls {
					s.Labels[lp.GetName()] = lp.GetValue()
				}
			}
			out = append(out, s)
		}
	}
	return out
}

// buildOutput assembles the final JSON document from raw probe results.
func buildOutput(version, target string, results []probeResult) output {
	o := output{Version: version, Target: target}
	o.Summary.Total = len(results)

	first := true
	var sum float64
	for _, r := range results {
		o.Results = append(o.Results, resultJSON{
			Module:   r.module,
			Prober:   r.prober,
			Attempt:  r.attempt,
			Success:  r.success,
			Duration: r.duration,
			Metrics:  familiesToSamples(r.families),
			Debug:    r.debug,
		})
		if r.success {
			o.Summary.Succeeded++
		} else {
			o.Summary.Failed++
		}
		d := r.duration
		if first {
			o.Summary.Latency.Min, o.Summary.Latency.Max = d, d
			first = false
		} else {
			if d < o.Summary.Latency.Min {
				o.Summary.Latency.Min = d
			}
			if d > o.Summary.Latency.Max {
				o.Summary.Latency.Max = d
			}
		}
		sum += d
	}
	if o.Summary.Total > 0 {
		o.Summary.Latency.Avg = sum / float64(o.Summary.Total)
		if o.Summary.Failed == 0 {
			o.Summary.ProbeSuccess = 1
		}
	}
	return o
}

// writeProm emits the standard Prometheus text exposition of the gathered
// families. Intended for single-module/single-attempt scrapes; with multiple
// results the blocks are concatenated in order.
func writeProm(w io.Writer, results []probeResult) error {
	enc := expfmt.NewEncoder(w, expfmt.NewFormat(expfmt.TypeTextPlain))
	for _, r := range results {
		for _, mf := range r.families {
			if err := enc.Encode(mf); err != nil {
				return err
			}
		}
	}
	return nil
}
