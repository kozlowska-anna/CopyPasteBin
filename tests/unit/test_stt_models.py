import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from copypastebin.stt_models import (
    ModelArtifactError,
    ModelManifestError,
    load_model_manifest,
    verify_local_artifact,
)


class SpeechModelManifestTests(unittest.TestCase):
    def test_bundled_catalog_separates_model_and_engine_versions(self):
        models = {model.model_id: model for model in load_model_manifest()}
        whisper = models["whisper.cpp-tiny-multilingual"]
        self.assertTrue(whisper.download.enabled)
        self.assertEqual(("1.9.5",), whisper.engine.versions)
        self.assertEqual("tiny@5359861c739e955e79d9a303bcbc70fb988958b1", whisper.model_version)
        self.assertEqual("single-file", whisper.download.artifact_format)

    def test_vosk_download_is_blocked_without_independent_integrity(self):
        models = {model.model_id: model for model in load_model_manifest()}
        vosk = models["vosk-small-pl-0.22"]
        self.assertFalse(vosk.download.enabled)
        self.assertIsNone(vosk.download.sha256)
        self.assertIn("disabled", vosk.download.limitation)

    def test_local_synthetic_artifact_is_verified_without_network(self):
        payload = b"synthetic-model-content"
        document = self._fake_manifest(payload)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(document), encoding="utf-8")
            artifact = root / "fake-model.bin"
            artifact.write_bytes(payload)
            model = load_model_manifest(manifest)[0]
            verify_local_artifact(artifact, model)
            artifact.write_bytes(payload + b"changed")
            with self.assertRaises(ModelArtifactError):
                verify_local_artifact(artifact, model)

    def test_symlinked_manifest_and_artifact_are_rejected(self):
        payload = b"synthetic-model-content"
        document = self._fake_manifest(payload)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest-target.json"
            manifest.write_text(json.dumps(document), encoding="utf-8")
            manifest_link = root / "manifest.json"
            manifest_link.symlink_to(manifest)
            with self.assertRaises(ModelManifestError):
                load_model_manifest(manifest_link)
            artifact = root / "artifact-target.bin"
            artifact.write_bytes(payload)
            artifact_link = root / "artifact.bin"
            artifact_link.symlink_to(artifact)
            with self.assertRaises(ModelArtifactError):
                verify_local_artifact(artifact_link, load_model_manifest(manifest)[0])

    def test_manifest_rejects_http_unknown_fields_and_parent_paths(self):
        payload = b"synthetic-model-content"
        mutations = (
            lambda document: document["models"][0]["download"].update(
                source_url="http://example.invalid/model.bin"
            ),
            lambda document: document["models"][0].update(unknown=True),
            lambda document: document["models"][0].update(
                install_relative_path="../outside.bin"
            ),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as directory:
                document = self._fake_manifest(payload)
                mutate(document)
                path = Path(directory) / "manifest.json"
                path.write_text(json.dumps(document), encoding="utf-8")
                with self.assertRaises(ModelManifestError):
                    load_model_manifest(path)

    def test_manifest_version_requires_exact_integer_one(self):
        payload = b"synthetic-model-content"
        versions = (True, False, "1", 2)
        for version in versions:
            with self.subTest(version=version), tempfile.TemporaryDirectory() as directory:
                document = self._fake_manifest(payload)
                document["version"] = version
                path = Path(directory) / "manifest.json"
                path.write_text(json.dumps(document), encoding="utf-8")
                with self.assertRaises(ModelManifestError):
                    load_model_manifest(path)

        with tempfile.TemporaryDirectory() as directory:
            document = self._fake_manifest(payload)
            del document["version"]
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(ModelManifestError):
                load_model_manifest(path)

    @staticmethod
    def _fake_manifest(payload: bytes) -> dict:
        return {
            "version": 1,
            "models": [{
                "id": "fake-pl",
                "model_version": "test-1",
                "name": {"pl": "Model testowy", "en": "Test model"},
                "language": {
                    "code": "pl",
                    "name": {"pl": "polski", "en": "Polish"},
                },
                "engine": {"id": "fake-engine", "compatible_versions": ["1"]},
                "download": {
                    "enabled": True,
                    "source_url": "https://example.invalid/model.bin",
                    "bytes": len(payload),
                    "required_disk_bytes": len(payload) * 2,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "format": "single-file",
                    "limitation": None,
                },
                "license": {"id": "CC0-1.0", "url": "https://example.invalid/license"},
                "install_relative_path": "fake/1/model.bin",
                "approximate_ram_mib": 1,
            }],
        }


if __name__ == "__main__":
    unittest.main()
