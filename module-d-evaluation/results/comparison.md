# CASPER - reactive vs predictive

Same traffic curve, same infrastructure, same scale controller -- only
the scaling strategy differs.

| Metric | Reactive | Predictive (CASPER) | Better |
|---|---|---|---|
| p95 response time (ms) | 2063 | 121 | predictive |
| median response time (ms) | 91 | 75 | - |
| error rate | 5.18% | 0.00% | predictive |
| % successful requests | 93.90% | 100.00% | predictive |
| requests sent | 31536 | 31847 | - |
| dropped (never sent) | 311 | 0 | - |
| replica-seconds (cost) | 623 | 706 | reactive |

p95 reduction with CASPER: **94.2%**

Replica-seconds is the honest cost of predicting: CASPER provisions
before the traffic arrives, so some of that capacity sits idle first.
