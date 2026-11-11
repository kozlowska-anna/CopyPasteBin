import json
import sys


session = sys.argv[1]
frames = (
    {"version": 1, "session_id": session, "sequence": 1, "kind": "ready"},
    {"version": 1, "session_id": session, "sequence": 2, "kind": "partial",
     "segment": 0, "text": "To jest"},
    {"version": 1, "session_id": session, "sequence": 3, "kind": "final",
     "segment": 0, "text": "To jest syntetyczna próba lokalnego dyktowania."},
    {"version": 1, "session_id": session, "sequence": 4, "kind": "stopped"},
)
for frame in frames:
    print(json.dumps(frame, ensure_ascii=False), flush=True)
