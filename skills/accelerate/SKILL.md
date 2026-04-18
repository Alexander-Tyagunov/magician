---
name: accelerate
description: Performance profiling with mandatory baseline-first discipline — no optimization without measurement
keep-coding-instructions: true
---

# /accelerate — Performance Profiling

Profile and optimize performance systematically. No optimization without measurement.

<HARD-GATE>
Establish a baseline measurement BEFORE making any changes. Optimization without a baseline is guesswork.
</HARD-GATE>

## Process

### Phase 1: Define the Target

Ask both questions in one message:
> "Before I start profiling, two quick questions:
> 1. What specifically is slow? (page load, API response, query, computation — be as specific as possible)
> 2. What's the acceptable performance target? (e.g., 'under 200ms', 'p99 < 500ms')"

**End your turn. Wait for both answers before proceeding to Phase 2. Do not run any benchmarks until you have a defined target.**

### Phase 2: Baseline
Measure current performance using the appropriate tool:

**API:**
```bash
wrk -t4 -c100 -d30s http://localhost:8080/api/endpoint
# or: hey -n 1000 -c 50 http://localhost:8080/api/endpoint
```

**Web (browser):**
```bash
npx lighthouse http://localhost:3000 --output json --output-path baseline.json
```

**Python:**
```python
import cProfile, pstats
profiler = cProfile.Profile()
profiler.enable()
# ... run the slow code ...
profiler.disable()
stats = pstats.Stats(profiler).sort_stats('cumulative')
stats.print_stats(20)
```

**Go:**
```go
import _ "net/http/pprof"
// Then: go tool pprof http://localhost:6060/debug/pprof/profile
```

Record baseline numbers.

### Phase 3: Profile to Find Bottleneck
Use the profiler to identify the actual bottleneck. The bottleneck is where the most time is spent — not the most obvious place.

### Phase 4: Targeted Fix
Fix ONLY the identified bottleneck. Common fixes:
- DB: add index, use JOIN instead of N+1, batch queries
- API: cache response, reduce payload size, move work async
- Frontend: code splitting, lazy loading, image optimization
- Computation: use better algorithm, vectorize, parallelize

### Phase 5: Measure Again
Run the same benchmark as Phase 2. Compare: baseline vs. optimized.
If target not met: return to Phase 3.

## Completion Signal

"Accelerate complete. Baseline: <N>. Optimized: <N>. Improvement: <X>%. Target <met/not met>."
