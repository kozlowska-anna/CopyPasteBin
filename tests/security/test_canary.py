import io
import tempfile
import unittest
from pathlib import Path

from copypastebin.application import inspect_and_record
from copypastebin.bridge import observe_framed_event
from copypastebin.detection import analyze_text
from copypastebin.filters import FilterError, FilterStore
from copypastebin.history import HistoryStore
from copypastebin.models import Category
from copypastebin.pause import PAUSE_30_MINUTES, PauseError, PauseStore
from copypastebin.ui import UiError, detections_json, history_json, redacted_suggestion


class CanaryTests(unittest.TestCase):
    def test_editor_canary_absent_from_suggestion_history_and_errors(self):
        canary = "EDITOR_PRIVATE_CANARY\x1b\u202e"
        text = "password=" + canary
        with tempfile.TemporaryDirectory() as directory:
            history = HistoryStore(Path(directory) / "state")
            inspect_and_record(
                text,
                source_kind="clipboard_event",
                purpose="other",
                history=history,
            )
            rendered = (
                history_json(history)
                + redacted_suggestion(text)
                + detections_json(analyze_text(text))
            )
            error = UiError()
            rendered += str(error) + repr(error)
            self.assertNotIn(canary, rendered)
            for path in history.state_dir.iterdir():
                if path.is_file():
                    self.assertNotIn(canary.encode(), path.read_bytes())

    def test_event_bridge_canary_absent_from_history_result_and_repr(self):
        canary = "EVENT_BRIDGE_PRIVATE_CANARY\x1b\u202e"
        app = b"org.mozilla.firefox"
        payload = len(app).to_bytes(4, "big") + app + ("password=" + canary).encode()

        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state"
            history = HistoryStore(state)
            result = observe_framed_event(
                io.BytesIO(payload),
                history=history,
                pause=PauseStore(state),
            )
            rendered = repr(history.recent()) + repr(result)
            self.assertNotIn(canary, rendered)
            for path in state.iterdir():
                if path.is_file():
                    self.assertNotIn(canary.encode(), path.read_bytes())

    def test_pause_state_contains_no_clipboard_canary_and_errors_are_redacted(self):
        canary = "PAUSE_CLIPBOARD_PRIVATE_CANARY\x1b\u202e"
        with tempfile.TemporaryDirectory() as directory:
            store = PauseStore(Path(directory) / "state", clock=lambda: 2_000_000_000)
            store.pause_for(PAUSE_30_MINUTES)
            self.assertNotIn(canary.encode(), store.state_path.read_bytes())
            store.state_path.write_text(canary, encoding="utf-8")
            store.state_path.chmod(0o600)
            with self.assertRaises(PauseError) as caught:
                store.status()
            self.assertNotIn(canary, str(caught.exception) + repr(caught.exception))

    def test_filter_state_contains_no_clipboard_canary_and_errors_are_redacted(self):
        canary = "FILTER_CLIPBOARD_PRIVATE_CANARY\x1b\u202e"
        with tempfile.TemporaryDirectory() as directory:
            store = FilterStore(Path(directory) / "state")
            store.set_enabled(Category.HOME_PATH, False)
            store.set_auto_clear(60)
            self.assertNotIn(canary.encode(), store.state_path.read_bytes())
            store.state_path.write_text(canary, encoding="utf-8")
            store.state_path.chmod(0o600)
            with self.assertRaises(FilterError) as caught:
                store.status()
            self.assertNotIn(canary, str(caught.exception) + repr(caught.exception))

    def test_canary_absent_from_history_repr_and_files(self):
        canary = "SYNTHETIC_PRIVATE_CANARY\x1b\u202e"
        text = "password=" + canary
        with tempfile.TemporaryDirectory() as directory:
            store = HistoryStore(Path(directory) / "state")
            operation = inspect_and_record(text, source_kind="stdin", purpose="chat", history=store)
            entry = store.get(operation.operation_id)
            combined = repr(operation) + repr(operation.analysis) + repr(operation.analysis.detections) + repr(entry)
            self.assertNotIn(canary, combined)
            for path in store.state_dir.iterdir():
                if path.is_file():
                    self.assertNotIn(canary.encode(), path.read_bytes())

    def test_detection_repr_does_not_expose_positions_or_input(self):
        canary = "SYNTHETIC_PRIVATE_CANARY"
        operation_text = "password=" + canary
        with tempfile.TemporaryDirectory() as directory:
            result = inspect_and_record(operation_text, source_kind="stdin", purpose="chat", history=HistoryStore(Path(directory) / "state"))
        self.assertNotIn(canary, repr(result.analysis.detections[0]))
        self.assertNotIn("start=", repr(result.analysis.detections[0]))
