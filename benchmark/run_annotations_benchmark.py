#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Any
from typing import Optional
from urllib import error, request
import uuid


def _normalize(text: str) -> list[str]:
    clean = "".join(ch.lower() if ch.isalnum() else " " for ch in text)
    return [t for t in clean.split() if t]


def _token_overlap(expected: str, actual: str) -> float:
    exp_tokens = set(_normalize(expected))
    if not exp_tokens:
        return 0.0
    act_tokens = set(_normalize(actual))
    if not act_tokens:
        return 0.0
    return len(exp_tokens.intersection(act_tokens)) / len(exp_tokens)


def _multipart_body(pdf_bytes: bytes, config_json: str) -> tuple[bytes, str]:
    boundary = f"----ragbench{uuid.uuid4().hex}"
    parts: list[bytes] = []
    parts.append(
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="config"\r\n\r\n'
            f"{config_json}\r\n"
        ).encode("utf-8")
    )
    parts.append(
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="Project_3_Offloading.pdf"\r\n'
            "Content-Type: application/pdf\r\n\r\n"
        ).encode("utf-8")
        + pdf_bytes
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts), boundary


def _call_annotations(
    host: str,
    pdf_path: Path,
    rules: list[dict[str, Any]],
    timeout_s: float,
    chunk_length: Optional[int],
) -> dict[str, Any]:
    with pdf_path.open("rb") as f:
        pdf_bytes = f.read()

    cfg: dict[str, Any] = {
        "rules": [{"id": r["id"], "termsRaw": r["termsRaw"]} for r in rules]
    }
    if chunk_length is not None:
        cfg["chunkLength"] = int(chunk_length)
    config_json = json.dumps(cfg)
    body, boundary = _multipart_body(pdf_bytes, config_json)

    url = host.rstrip("/") + "/api/annotations"
    req = request.Request(
        url=url,
        method="POST",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _score_run(
    payload: dict[str, Any],
    rules: list[dict[str, Any]],
    match_threshold: float,
) -> tuple[float, dict[str, float], dict[str, list[str]]]:
    by_rule: dict[str, list[str]] = {rule["id"]: [] for rule in rules}
    for match in payload.get("matches", []):
        rule_id = str(match.get("id", ""))
        text = str(match.get("text", "")).strip()
        if rule_id in by_rule and text:
            by_rule[rule_id].append(text)

    rule_scores: dict[str, float] = {}
    for rule in rules:
        rule_id = str(rule["id"])
        expected_items = [str(x) for x in rule.get("expected", [])]
        if not expected_items:
            rule_scores[rule_id] = 0.0
            continue

        hits = 0
        actual_items = by_rule.get(rule_id, [])
        for expected in expected_items:
            best = max((_token_overlap(expected, actual) for actual in actual_items), default=0.0)
            if best >= match_threshold:
                hits += 1
        rule_scores[rule_id] = (hits / len(expected_items)) * 100.0

    overall = sum(rule_scores.values()) / len(rule_scores)
    return overall, rule_scores, by_rule


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark /api/annotations against hardcoded expected spans.")
    parser.add_argument("host", help="API host, e.g. http://localhost:8080")
    parser.add_argument(
        "--ground-truth",
        default="ground_truth_project_3_offloading.json",
        help="Path to benchmark config and expected phrases JSON.",
    )
    parser.add_argument("-x", "--runs", type=int, default=3, help="How many repeated runs to execute.")
    parser.add_argument(
        "--pass-threshold",
        type=float,
        default=70.0,
        help="Average score percent required to pass.",
    )
    parser.add_argument(
        "--match-threshold",
        type=float,
        default=0.6,
        help="Per-phrase token overlap threshold (0..1).",
    )
    parser.add_argument("--timeout", type=float, default=120.0, help="Request timeout in seconds.")
    parser.add_argument(
        "--chunk-length",
        type=int,
        default=None,
        help="Optional chunk length to send in request config.",
    )
    args = parser.parse_args()

    if args.runs < 1:
        raise SystemExit("--runs must be >= 1")
    if not (0.0 <= args.match_threshold <= 1.0):
        raise SystemExit("--match-threshold must be between 0 and 1")
    if args.chunk_length is not None and args.chunk_length < 32:
        raise SystemExit("--chunk-length must be >= 32")

    gt_path = Path(args.ground_truth)
    if not gt_path.exists():
        raise SystemExit(f"Ground truth file not found: {gt_path}")
    gt = json.loads(gt_path.read_text(encoding="utf-8"))

    pdf_path = Path(str(gt.get("pdf_path", "")).strip())
    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")

    rules = gt.get("rules", [])
    if not isinstance(rules, list) or len(rules) != 4:
        raise SystemExit("Ground truth must contain exactly 4 rules.")

    run_totals: list[float] = []
    last_rule_scores: dict[str, float] = {}
    last_texts: dict[str, list[str]] = {}

    for run_idx in range(1, args.runs + 1):
        try:
            payload = _call_annotations(
                args.host,
                pdf_path,
                rules,
                args.timeout,
                args.chunk_length,
            )
        except error.URLError as exc:
            print(f"Run {run_idx}: request failed: {exc}")
            return 3
        except Exception as exc:
            print(f"Run {run_idx}: unexpected error: {exc}")
            return 3

        total, rule_scores, texts = _score_run(payload, rules, args.match_threshold)
        run_totals.append(total)
        last_rule_scores = rule_scores
        last_texts = texts
        print(f"Run {run_idx}/{args.runs}: score={total:.1f}%")

    avg = sum(run_totals) / len(run_totals)
    verdict = "PASS" if avg >= args.pass_threshold else "FAIL"
    print("")
    print(f"PDF: {pdf_path}")
    if args.chunk_length is not None:
        print(f"Chunk length: {args.chunk_length}")
    print(f"Average score: {avg:.1f}% (threshold {args.pass_threshold:.1f}%) => {verdict}")
    print("Per-rule score from last run:")
    for rule in rules:
        rid = str(rule["id"])
        print(f"  - {rid}: {last_rule_scores.get(rid, 0.0):.1f}%")

    print("Captured match text from last run:")
    for rule in rules:
        rid = str(rule["id"])
        values = last_texts.get(rid, [])
        if values:
            for v in values:
                print(f"  - {rid}: {v}")
        else:
            print(f"  - {rid}: <none>")

    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
