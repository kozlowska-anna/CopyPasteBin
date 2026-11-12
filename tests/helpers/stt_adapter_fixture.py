import json
import sys
import time


session = sys.argv[1]
realtime = len(sys.argv) == 3 and sys.argv[2] == "realtime"
frames = (
    {"version": 1, "session_id": session, "sequence": 1, "kind": "ready"},
    {"version": 1, "session_id": session, "sequence": 2, "kind": "partial",
     "segment": 0, "text": "To jest", "audio_position_ms": 50},
    {"version": 1, "session_id": session, "sequence": 3, "kind": "final",
     "segment": 0, "text": "To jest syntetyczna próba lokalnego dyktowania.",
     "audio_position_ms": 100},
    {"version": 1, "session_id": session, "sequence": 4, "kind": "stopped",
     "audio_position_ms": 100},
)
for index, frame in enumerate(frames):
    if realtime and index in {1, 2}:
        time.sleep(0.05)
    print(json.dumps(frame, ensure_ascii=False), flush=True)
