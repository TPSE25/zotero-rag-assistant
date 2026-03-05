# Annotations Benchmark

Runs an external benchmark against `POST /api/annotations` using the provided PDF

## Run

```bash
python3 benchmark/run_annotations_benchmark.py http://localhost:8080 -x 5 --pass-threshold 70
```

Optional request chunk size:

```bash
python3 benchmark/run_annotations_benchmark.py http://localhost:8080 -x 5 --chunk-length 1200
```

## Ground Truth

`ground_truth_project_3_offloading.json`

This file contains:

- `pdf_path`: input PDF
- 4 rules (including one semantic non-test category)
- hardcoded expected snippets used for scoring
