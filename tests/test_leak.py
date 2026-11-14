from pathlib import Path

from leak import find_leaked_tokens


ROOT = Path(__file__).parent / "fixtures" / "leak"
FILES = {
    "/fleet/odd_columns.csv": ROOT / "token_fingerprints.csv",
    "/intel/paste_dump.txt": ROOT / "paste_dump.txt",
    "/board/posts.jsonl": ROOT / "board.jsonl",
}
READ = lambda path: FILES[path].read_bytes()


hits = find_leaked_tokens(READ, set(FILES), ["/intel/paste_dump.txt"])
assert hits == [
    {"token": "TOK-FULL-01", "path": "/intel/paste_dump.txt", "line": 2},
    {"token": "TOK-SPLIT-02", "path": "/intel/paste_dump.txt", "line": 3, "end_line": 4},
]

assert [hit["token"] for hit in find_leaked_tokens(READ, set(FILES))] == [
    "TOK-BOARD-03", "TOK-FULL-01", "TOK-SPLIT-02"
]
print("test_leak: ok")
