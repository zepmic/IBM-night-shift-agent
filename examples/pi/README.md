# Reference harness: pi + the fixed small model

A second baseline next to `agent.py`: the [pi coding agent](https://www.npmjs.com/package/@mariozechner/pi-coding-agent)
(bash, read, edit, write tools) driving the fixed small model (`ARENA_MAIN_MODEL`) on each task.

How it works, per task:

1. `run_pi.py` downloads the task's `workspace.zip` and unpacks it into `runs/pi/<run>/<task>/workspace/`.
2. pi runs there non-interactively (`pi -p`), with the workspace's AGENTS.md appended to its system prompt as operator
   rules. It inspects files with bash and Python (pypdf, python-docx and openpyxl from this kit's virtualenv) and looks at
   images with its vision-capable `read` tool.
3. Everything that touches the platform goes through the `arena` command (`arena_cli.py`): `arena tools`,
   `arena tool <name> '<json args>'` (weather, route, get_plan, update_plan, send_message, write, …) and
   `arena submit '<json>'`.

```bash
npm i -g @mariozechner/pi-coding-agent         # or: PI_BIN=/path/to/node_modules/.bin/pi
export OPENROUTER_API_KEY=… ARENA_API_KEY=… ARENA_BASE_URL=…
uv run examples/pi/run_pi.py --kind dev --parallel 5 --budget 1.0 --note "pi baseline"
uv run examples/pi/run_pi.py --kind dev --tasks t01,t02 --thinking medium --note "medium thinking on t01, t02"
```

`pi-agent/models.json` registers the fixed model for pi's OpenRouter provider (with the pinned provider's prices, so pi's
cost tally is right; add an entry there if `ARENA_MAIN_MODEL` names another model). pi reads environment variables
only in `apiKey` and `headers`, so `run_pi.py` writes a copy to `runs/pi/<run>/pi-agent/` with `baseUrl` set from
`OPENROUTER_BASE_URL` (default `https://openrouter.ai/api/v1`) and points pi at it with `PI_CODING_AGENT_DIR`. It also
turns off pi's own context-file, skill and extension discovery so only the workspace rules are loaded. Transcripts (`pi.jsonl`) and a `summary.json` land in `runs/pi/<run>/`.

It is a generic harness: no task-specific code, no verification step, no Jev. Teams are free to use pi (or any other
agent framework) as long as the only models are the fixed small model and Jev through their team keys.
