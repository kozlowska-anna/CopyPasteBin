import tempfile
import unittest
from pathlib import Path

from copypastebin.config import (
    ConfigError,
    load_custom_rules,
    load_customizations,
    save_custom_rules,
    save_customizations,
)
from copypastebin.detection import (
    CustomLiteralExclusion,
    CustomLiteralRule,
    analyze_text,
)
from copypastebin.models import Category, RiskLevel


class ConfigTests(unittest.TestCase):
    def test_missing_config_means_no_custom_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual((), load_custom_rules(Path(directory) / "missing.toml"))
            self.assertEqual(
                ((), ()),
                load_customizations(Path(directory) / "missing.toml"),
            )

    def test_literal_rule_is_closed_and_does_not_expose_literal_in_repr(self):
        canary = "SYNTHETIC-MARKER"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(f'version = 1\n[[rules]]\nliteral = "{canary}"\nrisk = "warning"\n', encoding="utf-8")
            rules = load_custom_rules(path)
        result = analyze_text("prefix " + canary + " suffix", rules)
        self.assertEqual(Category.CUSTOM_RULE, result.detections[0].category)
        self.assertEqual(RiskLevel.WARNING, result.highest_risk)
        self.assertNotIn(canary, result.redacted_text)
        self.assertNotIn(canary, repr(rules))

    def test_invalid_or_dangerous_configuration_fails_closed(self):
        documents = (
            'version = true\n',
            'version = 4\n',
            'version = 1\nunknown = 1\n',
            'version = 1\n[[rules]]\nliteral = "ab"\nrisk = "warning"\n',
            'version = 1\n[[rules]]\nliteral = "abc"\nrisk = "information"\n',
            'version = 1\n[[rules]]\nliteral = "abc\\u001b"\nrisk = "high"\n',
            'version = 2\n[[exclusions]]\nliteral = "ab"\nenabled = true\n',
            'version = 2\n[[exclusions]]\nliteral = "abc\\u001b"\nenabled = true\n',
            'version = 2\n[[rules]]\nliteral = "duplicate"\nrisk = "warning"\n[[exclusions]]\nliteral = "duplicate"\nenabled = true\n',
        )
        for document in documents:
            with self.subTest(document=document), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "config.toml"
                path.write_text(document, encoding="utf-8")
                with self.assertRaises(ConfigError):
                    load_custom_rules(path)

    def test_symlink_config_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.toml"
            target.write_text("version = 1\n", encoding="utf-8")
            link = root / "config.toml"
            link.symlink_to(target)
            with self.assertRaises(ConfigError):
                load_custom_rules(link)

    def test_rules_are_saved_atomically_privately_and_round_trip(self):
        rules = (
            CustomLiteralRule("SYNTHETIC-MARKER", RiskLevel.WARNING),
            CustomLiteralRule("INTERNAL-LABEL", RiskLevel.HIGH, False),
        )
        with tempfile.TemporaryDirectory() as directory:
            config_dir = Path(directory) / "copypastebin"
            path = config_dir / "config.toml"
            save_custom_rules(rules, path)
            self.assertEqual(rules, load_custom_rules(path))
            self.assertEqual(0o700, config_dir.stat().st_mode & 0o777)
            self.assertEqual(0o600, path.stat().st_mode & 0o777)
            self.assertEqual([], list(config_dir.glob(".*.tmp")))
            save_custom_rules((), path)
            self.assertEqual((), load_custom_rules(path))

    def test_rules_and_exclusions_are_saved_together_and_v1_is_migrated(self):
        rules = (CustomLiteralRule("SYNTHETIC-MARKER", RiskLevel.WARNING),)
        exclusions = (CustomLiteralExclusion(
            "5.6 Sol", Category.CRYPTO_AMOUNT_BTC_XRP
        ),)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "copypastebin" / "config.toml"
            path.parent.mkdir(mode=0o700)
            path.write_text(
                'version = 1\n[[rules]]\nliteral = "SYNTHETIC-MARKER"\nrisk = "warning"\n',
                encoding="utf-8",
            )
            self.assertEqual((rules, ()), load_customizations(path))
            save_customizations(rules, exclusions, path)
            self.assertEqual((rules, exclusions), load_customizations(path))
            self.assertIn("version = 3", path.read_text(encoding="ascii"))
            self.assertNotIn("5.6 Sol", repr(load_customizations(path)))

    def test_v2_exclusions_migrate_only_exact_low_or_medium_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(
                'version = 2\n'
                '[[exclusions]]\nliteral = "5.6 Sol"\nenabled = true\n'
                '[[exclusions]]\nliteral = "person@example.com"\nenabled = true\n'
                '[[exclusions]]\n'
                'literal = "sk-proj-CPBINSYNTHETIC0123456789abcdef"\n'
                'enabled = true\n',
                encoding="utf-8",
            )
            _, exclusions = load_customizations(path)
            self.assertEqual(
                (
                    CustomLiteralExclusion(
                        "5.6 Sol", Category.CRYPTO_AMOUNT_BTC_XRP
                    ),
                    CustomLiteralExclusion("person@example.com", Category.EMAIL),
                ),
                exclusions,
            )
            save_customizations((), exclusions, path)
            self.assertEqual(((), exclusions), load_customizations(path))
            rendered = path.read_text(encoding="ascii")
            self.assertIn('category = "EMAIL"', rendered)
            self.assertNotIn("sk-proj-", rendered)

    def test_high_and_critical_exclusion_categories_are_rejected(self):
        for category in (Category.OPENAI_API_KEY, Category.POSSIBLE_SEED_PHRASE):
            with self.subTest(category=category), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "copypastebin" / "config.toml"
                with self.assertRaises(ConfigError):
                    save_customizations(
                        (),
                        (CustomLiteralExclusion("SYNTHETIC-VALUE", category),),
                        path,
                    )

    def test_save_rejects_duplicate_invalid_and_symlink_targets(self):
        duplicate = (
            CustomLiteralRule("duplicate", RiskLevel.WARNING),
            CustomLiteralRule("duplicate", RiskLevel.HIGH),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ConfigError):
                save_custom_rules(duplicate, root / "config.toml")
            target = root / "target.toml"
            target.write_text("version = 1\n", encoding="utf-8")
            link = root / "link.toml"
            link.symlink_to(target)
            with self.assertRaises(ConfigError):
                save_custom_rules((), link)
