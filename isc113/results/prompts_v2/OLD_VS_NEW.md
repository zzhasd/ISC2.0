# Old versus prompts-v2 evaluation

Each rate cell shows old -> new. Inference mean tokens are unchanged.

## equivalent_only

| Method | Precision | Recall | Grounded Recall | Mean tokens |
|---|---:|---:|---:|---:|
| direct_thinking | 17.02% -> 11.55% | 26.36% -> 18.54% | 49.62% -> 39.31% | 1186.07 |
| direct_multisample_verifier | 17.84% -> 12.62% | 28.23% -> 20.24% | 56.87% -> 43.89% | 4488.44 |
| route1_only | 22.58% -> 16.90% | 24.66% -> 18.71% | 48.85% -> 40.46% | 1069.67 |
| route2_only | 11.78% -> 7.08% | 20.92% -> 13.10% | 37.79% -> 27.48% | 1238.24 |
| dual_without_verifier | 15.40% -> 10.50% | 31.12% -> 21.60% | 58.78% -> 45.80% | 2307.91 |
| dual_with_verifier | 17.61% -> 12.75% | 27.21% -> 19.90% | 54.20% -> 43.51% | 4281.91 |

## broader_counted_as_hit

| Method | Precision | Recall | Grounded Recall | Mean tokens |
|---|---:|---:|---:|---:|
| direct_thinking | 31.51% -> 36.13% | 44.39% -> 46.77% | 66.03% -> 69.85% | 1186.07 |
| direct_multisample_verifier | 33.58% -> 38.36% | 46.77% -> 47.45% | 71.37% -> 72.52% | 4488.44 |
| route1_only | 36.56% -> 38.40% | 37.59% -> 38.10% | 60.31% -> 59.54% | 1069.67 |
| route2_only | 27.51% -> 28.24% | 43.37% -> 42.52% | 57.25% -> 56.49% | 1238.24 |
| dual_without_verifier | 30.44% -> 31.56% | 56.12% -> 54.25% | 77.86% -> 75.57% | 2307.91 |
| dual_with_verifier | 33.31% -> 34.58% | 47.11% -> 45.58% | 70.61% -> 69.85% | 4281.91 |
