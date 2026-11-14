# The final run: setup and load test

What your final runs in, and what the organisers measured in a full rehearsal on the event infrastructure on
12 November: 17 test teams, up to 12 finals running at the same time, each in its own container, all traffic through
the same gateway as on the day.

## Setup

- **Your code:** your latest upload, built from the `Dockerfile` at its root (image up to 2 GB).
- **Limits per team:**
  - 2 CPUs.
  - 4 GB memory, no swap. Above it the process is killed (exit code 137).
  - 512 processes.
  - 4 GB written to the container's disk. Above it the container is stopped.
- **Time:** 30 minutes from the start of your final; then the container is stopped. Unsubmitted tasks score 0.
- **Network:** only the organisers' gateway, which forwards to the Task API and to OpenRouter. No other internet access.
- **Endpoint order:** the gateway sets it on every call, whatever your harness sends:
  - the fixed model: DeepInfra fp8, then Crusoe, then Novita (`PROVIDER_ORDER` in `arena/llm.py`);
  - embeddings (`qwen/qwen3-embedding-8b`): DeepInfra, then SiliconFlow.
- **Budget:** the final runs on an eval key with a $3 limit. At the limit OpenRouter answers 403 `Key limit exceeded`.
  The starter kit does not retry a 403, so its remaining tasks fail.
- **Task API rate limit:** about 20 requests/s per team (bursts up to 100). Above that it answers 429 with
  `Retry-After`.

## Measured with 12 finals running at once

| Endpoint | Calls | Median | 95th percentile | Errors |
|---|---|---|---|---|
| Fixed model (chat) | 4,592 | 3.0 s | 9.2 s (slowest 67 s) | none |
| Task API | 5,622 | 0.08 s | 0.18 s | none |
| Jev, 10 parallel calls on one key | 693 in 30 s | 0.4 s | 0.6 s | none |
| Jev, 25 to 100 parallel calls on one key | about 7 calls/s | 3 to 11 s | up to 24 s | none |
| Embeddings, 17 parallel clients, about 45k tokens per request | 136 | 7.8 s | 11.8 s | none |

A starter-kit final (default settings, `--parallel 4`) took 8 to 10 minutes and cost $0.66 to $0.81.

## What this means for your harness

- **Speed:** it isn't scored; accuracy and cost are. Answers can still take seconds: Jev when many calls run in
  parallel, the fixed model occasionally up to about a minute. Your run must finish within the 30 minutes.
- **Retries:** the kit retries 408, 429 and 5xx with backoff and honours `Retry-After`. That's `arena/llm.py` (up to
  5 retries, waits of 2 to 30 s, or what `Retry-After` asks for up to 2 minutes) and `arena/client.py` for the
  Task API. If you replace these clients, keep
  equivalent retries.
- **Restarts:** the rehearsal also restarted the gateway (back after about 7 s) and the runner while finals were
  running. No final failed.
