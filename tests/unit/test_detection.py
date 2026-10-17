from hashlib import sha256
from importlib.resources import files
import unittest
from unittest.mock import patch

from copypastebin.detection import (
    BIP39_RESOURCE_SHA256,
    CRYPTO_CURRENCIES,
    FIAT_CURRENCIES,
    Bip39ResourceError,
    CustomLiteralExclusion,
    CustomLiteralRule,
    analyze_text,
    load_bip39_words,
)
from copypastebin.models import Category, RiskLevel


class DetectionTests(unittest.TestCase):
    def categories(self, text):
        return [item.category for item in analyze_text(text).detections]

    def test_money_pln_approved_forms(self):
        forms = (
            "1234 PLN", "1 234,56 PLN", "1.234,56 PLN",
            "12.345,67 PLN", "1234 zł", "1 234,56 zł", "1.234,56 zł",
        )
        for form in forms:
            with self.subTest(form=form):
                result = analyze_text(form)
                self.assertEqual([Category.MONEY_AMOUNT_PLN_USD], self.categories(form))
                self.assertEqual("[MONEY_AMOUNT_PLN_USD_1]", result.redacted_text)
                self.assertEqual(RiskLevel.LOW, result.highest_risk)

    def test_money_usd_approved_forms(self):
        for form in ("1234 USD", "1,234.56 USD", "$1234.56", "$1,234.56"):
            with self.subTest(form=form):
                self.assertEqual([Category.MONEY_AMOUNT_PLN_USD], self.categories(form))

    def test_twenty_curated_fiat_currency_codes_are_detected(self):
        self.assertEqual(20, len(FIAT_CURRENCIES))
        self.assertEqual(20, len(set(FIAT_CURRENCIES)))
        for code in FIAT_CURRENCIES:
            with self.subTest(code=code):
                self.assertEqual(
                    [Category.MONEY_AMOUNT_PLN_USD],
                    self.categories(f"1234.56 {code}"),
                )

    def test_unambiguous_currency_symbols_are_detected(self):
        for form in ("€1234.56", "£1,234.56", "$1234.56"):
            with self.subTest(form=form):
                self.assertEqual([Category.MONEY_AMOUNT_PLN_USD], self.categories(form))

    def test_plain_numbers_and_ambiguous_usd_are_not_money(self):
        for value in ("1234", "2026-09-17", "version 1.2.3", "1 234.56 USD", "1.234,56 USD", "USD 1234", "1.234 567,89 PLN"):
            with self.subTest(value=value):
                self.assertNotIn(Category.MONEY_AMOUNT_PLN_USD, self.categories(value))

    def test_btc_and_xrp_amounts_are_warning_level_currency(self):
        forms = (
            "1 BTC",
            "0.00000001 btc",
            "1,5 BTC",
            "1 234,56 XRP",
            "1,234.56 xrp",
            "0.000001 XRP",
        )
        for form in forms:
            with self.subTest(form=form):
                result = analyze_text(form)
                self.assertEqual(
                    [Category.CRYPTO_AMOUNT_BTC_XRP],
                    [item.category for item in result.detections],
                )
                self.assertEqual("[CRYPTO_AMOUNT_BTC_XRP_1]", result.redacted_text)
                self.assertEqual(RiskLevel.LOW, result.highest_risk)

    def test_crypto_tickers_without_amount_are_not_currency_events(self):
        for value in ("BTC", "xrp", "BTC network", "XRP Ledger"):
            with self.subTest(value=value):
                self.assertNotIn(Category.CRYPTO_AMOUNT_BTC_XRP, self.categories(value))

    def test_twenty_curated_crypto_tickers_are_detected_only_with_amounts(self):
        self.assertEqual(20, len(CRYPTO_CURRENCIES))
        self.assertEqual(20, len(set(CRYPTO_CURRENCIES)))
        for code in CRYPTO_CURRENCIES:
            with self.subTest(code=code):
                self.assertEqual(
                    [Category.CRYPTO_AMOUNT_BTC_XRP],
                    self.categories(f"0.123456789012345678 {code}"),
                )
                self.assertNotIn(
                    Category.CRYPTO_AMOUNT_BTC_XRP,
                    self.categories(code),
                )

    def test_core_categories(self):
        cases = {
            "person@example.com": Category.EMAIL,
            "/home/alice/private.txt": Category.HOME_PATH,
            "192.0.2.10": Category.IP_ADDRESS,
            "https://user:pass@example.invalid/x": Category.URL_CREDENTIALS,
            "Authorization: Bearer abcdefghijklmnop": Category.AUTHORIZATION,
            "password=synthetic-only": Category.SECRET_ASSIGNMENT,
            "sk-abcdefghijklmnopqrstuv": Category.OPENAI_API_KEY,
            "+48 123 456 789": Category.PHONE,
        }
        for value, expected in cases.items():
            with self.subTest(expected=expected):
                self.assertIn(expected, self.categories(value))

    def test_provider_secret_library_uses_distinct_high_risk_categories(self):
        cases = {
            "sk-proj-CPBINSYNTHETIC0123456789abcdef": Category.OPENAI_API_KEY,
            "sk-ant-api03-CPBINSYNTHETIC0123456789abcdef": Category.ANTHROPIC_API_KEY,
            "AIza" + "CpbSynthetic_0123456789abcdefghijkl": Category.GOOGLE_API_KEY,
            "github_pat_CPBIN_SYNTHETIC_0123456789abcdef": Category.GITHUB_TOKEN,
            "xoxb-CPBINSYNTHETIC-0123456789": Category.SLACK_TOKEN,
            "sk_live_CPBINSYNTHETIC0123456789": Category.STRIPE_KEY,
            "AKIA" + "CPBINSYNTHETIC12": Category.AWS_ACCESS_KEY,
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiJzeW50aGV0aWMifQ.CPBINSYNTHETICSIGNATURE": Category.JWT,
            "postgresql://cpbin_user:synthetic_password@db.invalid/cpbin": Category.DATABASE_URL,
        }
        for value, category in cases.items():
            with self.subTest(category=category):
                result = analyze_text(value)
                self.assertIn(category, [item.category for item in result.detections])
                self.assertEqual(RiskLevel.HIGH, result.highest_risk)
                self.assertNotIn(value, result.redacted_text)

    def test_private_key_header_alone_is_critical(self):
        text = "-----BEGIN PRIVATE KEY-----\nCPBIN_SYNTHETIC_BODY"
        result = analyze_text(text)
        self.assertEqual([Category.PRIVATE_KEY], [item.category for item in result.detections])
        self.assertEqual(RiskLevel.CRITICAL, result.highest_risk)
        self.assertEqual("[PRIVATE_KEY_1]", result.redacted_text)

    def test_jwt_requires_a_structured_non_none_algorithm_header(self):
        for value in (
            "aaaaaaaa.bbbbbbbb.cccccccc",
            "eyJhbGciOiJub25lIn0.eyJzdWIiOiJzeW50aGV0aWMifQ.CPBINSIGNATURE",
        ):
            with self.subTest(value=value):
                self.assertNotIn(Category.JWT, self.categories(value))

    def test_valid_calendar_dates_are_not_detected_as_phones(self):
        dates = (
            "2026-09-24",
            "24-09-2026",
            "2026/09/24",
            "24/09/2026",
            "24.09.2026",
            "2024-02-29",
            "2026-09-24 23:20:45",
            "2026-09-24T23:20:45",
        )
        for value in dates:
            with self.subTest(value=value):
                self.assertNotIn(Category.PHONE, self.categories(value))

    def test_invalid_calendar_dates_keep_phone_detection(self):
        for value in ("2026-13-40", "2025-02-29"):
            with self.subTest(value=value):
                self.assertIn(Category.PHONE, self.categories(value))

    def test_date_exclusion_does_not_hide_a_phone_in_the_same_text(self):
        cases = (
            ("Raport 2026-09-24, telefon +48 501 234 567", "+48 501 234 567"),
            ("Raport 2026-09-24 501 234 567", "501 234 567"),
        )
        for text, expected_phone in cases:
            with self.subTest(text=text):
                result = analyze_text(text)
                phones = [
                    text[item.start:item.end]
                    for item in result.detections
                    if item.category is Category.PHONE
                ]
                self.assertEqual([expected_phone], phones)

    def test_existing_phone_formats_remain_detected(self):
        for value in (
            "+48 501 234 567",
            "501 234 567",
            "501-234-567",
            "501234567",
            "+1 202 555 0147",
            "telefon: 22 123 45 67",
        ):
            with self.subTest(value=value):
                self.assertIn(Category.PHONE, self.categories(value))

    def test_long_numeric_identifiers_are_not_split_into_phones(self):
        for value in (
            "1234-5678-9012-3456-7890-1234",
            "1234 5678 9012 3456 7890 1234",
            "123456-234567-345678-456789-567890",
            "123-456-789-012-345-678-901-234",
            "1234.5678.9012.3456.7890.1234",
        ):
            with self.subTest(value=value):
                self.assertNotIn(Category.PHONE, self.categories(value))

    def test_identifier_context_suppresses_only_ambiguous_phone_shapes(self):
        for value in (
            "ID: 501-234-567",
            "identyfikator 501 234 567",
            "order #501234567",
            "numer seryjny: 501-234-567",
        ):
            with self.subTest(value=value):
                self.assertNotIn(Category.PHONE, self.categories(value))
        for value in (
            "ID kontaktu: +48 501 234 567",
            "reference: (22) 123 45 67",
        ):
            with self.subTest(value=value):
                self.assertIn(Category.PHONE, self.categories(value))

    def test_phone_next_to_long_identifier_keeps_exact_range(self):
        text = "ID 1234-5678-9012-3456-7890-1234, tel. +48 501 234 567"
        phones = [
            text[item.start:item.end]
            for item in analyze_text(text).detections
            if item.category is Category.PHONE
        ]
        self.assertEqual(["+48 501 234 567"], phones)

    def test_space_separated_complete_phone_fields_are_recovered(self):
        cases = (
            ("ID 123456789 501234567", []),
            ("invoice 123456789 012345678", []),
            ("123456789 012345678", []),
            ("phone: 123456789 501234567", ["123456789", "501234567"]),
            ("501-234-567 600-700-800", ["501-234-567", "600-700-800"]),
            ("ID 123456789, tel. 501234567", ["501234567"]),
        )
        for text, expected in cases:
            with self.subTest(text=text):
                phones = [
                    text[item.start:item.end]
                    for item in analyze_text(text).detections
                    if item.category is Category.PHONE
                ]
                self.assertEqual(expected, phones)

    def test_checksum_validated_identity_and_payment_values(self):
        cases = {
            "44051401458": (Category.PESEL, RiskLevel.HIGH),
            "PL61 1090 1014 0000 0712 1981 2874": (Category.IBAN, RiskLevel.MEDIUM),
            "4111 1111 1111 1111": (Category.PAYMENT_CARD, RiskLevel.HIGH),
        }
        for value, (category, risk) in cases.items():
            with self.subTest(category=category):
                result = analyze_text(value)
                self.assertIn(category, [item.category for item in result.detections])
                self.assertEqual(risk, result.highest_risk)

    def test_bitlocker_recovery_key_is_high_risk_key_not_phone(self):
        groups = (
            "111111", "222222", "333333", "444444",
            "555555", "666666", "700007", "720885",
        )
        for value in ("-".join(groups), " ".join(groups), "".join(groups)):
            with self.subTest(separator=value[6:7]):
                result = analyze_text(value)
                self.assertEqual(
                    [Category.RECOVERY_KEY],
                    [item.category for item in result.detections],
                )
                self.assertEqual(RiskLevel.CRITICAL, result.highest_risk)
                self.assertEqual("[RECOVERY_KEY_1]", result.redacted_text)

    def test_bitlocker_checksum_and_filter_do_not_fall_back_to_phone(self):
        valid = (
            "111111-222222-333333-444444-"
            "555555-666666-700007-720885"
        )
        invalid = valid[:-1] + "4"
        self.assertNotIn(Category.RECOVERY_KEY, self.categories(invalid))
        disabled = analyze_text(
            valid,
            disabled_categories=frozenset({Category.RECOVERY_KEY}),
        )
        self.assertEqual((), disabled.detections)
        self.assertEqual(valid, disabled.redacted_text)

    def test_labeled_recovery_keys_use_general_key_category(self):
        for text in (
            "Recovery key: SYNTHETIC-APPLE-RECOVERY-2026",
            "Recovery code = synthetic_systemd_recovery_2026",
            "Klucz odzyskiwania: SYNTHETIC-KEY-123456",
        ):
            with self.subTest(text=text.split(":", 1)[0]):
                result = analyze_text(text)
                self.assertEqual(
                    [Category.RECOVERY_KEY],
                    [item.category for item in result.detections],
                )
                self.assertEqual(RiskLevel.CRITICAL, result.highest_risk)
                self.assertIn("[RECOVERY_KEY_1]", result.redacted_text)

    def test_invalid_checksums_are_not_identity_or_payment_detections(self):
        cases = {
            "44051401459": Category.PESEL,
            "PL62 1090 1014 0000 0712 1981 2874": Category.IBAN,
            "4111 1111 1111 1112": Category.PAYMENT_CARD,
        }
        for value, category in cases.items():
            with self.subTest(category=category):
                self.assertNotIn(category, self.categories(value))

    def test_adjacent_checksum_values_keep_their_own_boundaries(self):
        text = (
            "44051401458 PL61 1090 1014 0000 0712 1981 2874 "
            "4111 1111 1111 1111"
        )
        result = analyze_text(text)
        self.assertEqual(
            [Category.PESEL, Category.IBAN, Category.PAYMENT_CARD],
            [item.category for item in result.detections],
        )

    def test_disabled_custom_rule_remains_configured_but_does_not_detect(self):
        rules = (
            CustomLiteralRule("VISIBLE-MARKER", RiskLevel.WARNING, True),
            CustomLiteralRule("DISABLED-MARKER", RiskLevel.HIGH, False),
        )
        result = analyze_text("VISIBLE-MARKER DISABLED-MARKER", rules)
        self.assertEqual([Category.CUSTOM_RULE], [item.category for item in result.detections])
        self.assertIn("DISABLED-MARKER", result.redacted_text)

    def test_exact_literal_exclusion_suppresses_only_the_matching_false_positive(self):
        text = "Modele: 5.6 Sol, 5.6 SOL; portfel: 1 SOL"
        exclusions = (CustomLiteralExclusion("5.6 Sol", Category.CRYPTO_AMOUNT_BTC_XRP),)
        result = analyze_text(text, custom_exclusions=exclusions)
        detected = [
            text[item.start:item.end]
            for item in result.detections
            if item.category is Category.CRYPTO_AMOUNT_BTC_XRP
        ]
        self.assertEqual(["5.6 SOL", "1 SOL"], detected)
        self.assertIn("5.6 Sol", result.redacted_text)

    def test_partial_or_disabled_literal_exclusion_does_not_hide_detection(self):
        for exclusion in (
            CustomLiteralExclusion("Sol", Category.CRYPTO_AMOUNT_BTC_XRP),
            CustomLiteralExclusion("5.6 Sol", Category.CRYPTO_AMOUNT_BTC_XRP, False),
        ):
            with self.subTest(exclusion=repr(exclusion)):
                result = analyze_text(
                    "5.6 Sol",
                    custom_exclusions=(exclusion,),
                )
                self.assertEqual(
                    [Category.CRYPTO_AMOUNT_BTC_XRP],
                    [item.category for item in result.detections],
                )

    def test_invalid_literal_exclusion_is_rejected_before_scanning(self):
        for exclusion in (
            CustomLiteralExclusion("", Category.EMAIL),
            CustomLiteralExclusion("ab", Category.EMAIL),
            CustomLiteralExclusion("valid", Category.EMAIL, 1),
            CustomLiteralExclusion("valid", Category.OPENAI_API_KEY),
        ):
            with self.subTest(exclusion=repr(exclusion)), self.assertRaises(TypeError):
                analyze_text("5.6 Sol", custom_exclusions=(exclusion,))

    def test_literal_exclusion_does_not_hide_an_adjacent_detection(self):
        text = "5.6 Sol person@example.com"
        result = analyze_text(
            text,
            custom_exclusions=(CustomLiteralExclusion(
                "5.6 Sol", Category.CRYPTO_AMOUNT_BTC_XRP
            ),),
        )
        self.assertEqual(
            [Category.EMAIL],
            [item.category for item in result.detections],
        )

    def test_exclusion_is_bound_to_category_and_cannot_hide_high_or_critical(self):
        email = "person@example.com"
        wrong_category = CustomLiteralExclusion(email, Category.PHONE)
        self.assertEqual(
            [Category.EMAIL],
            [item.category for item in analyze_text(
                email, custom_exclusions=(wrong_category,)
            ).detections],
        )
        for text, category in (
            ("sk-proj-CPBINSYNTHETIC0123456789abcdef", Category.OPENAI_API_KEY),
            ("abandon " * 11 + "about", Category.POSSIBLE_SEED_PHRASE),
        ):
            with self.subTest(category=category), self.assertRaises(TypeError):
                analyze_text(
                    text,
                    custom_exclusions=(CustomLiteralExclusion(text, category),),
                )

    def test_disabled_categories_are_absent_from_detection_and_redaction(self):
        text = "person@example.com 1234 PLN /home/example/private.txt"
        disabled = frozenset(
            {Category.HOME_PATH, Category.MONEY_AMOUNT_PLN_USD}
        )
        result = analyze_text(text, disabled_categories=disabled)
        self.assertEqual([Category.EMAIL], [item.category for item in result.detections])
        self.assertIn("[EMAIL_1]", result.redacted_text)
        self.assertIn("1234 PLN", result.redacted_text)
        self.assertIn("/home/example/private.txt", result.redacted_text)

    def test_disabled_categories_parameter_is_closed(self):
        for invalid in ({Category.EMAIL}, frozenset({"EMAIL"}), None):
            with self.subTest(invalid=invalid), self.assertRaises(TypeError):
                analyze_text("person@example.com", disabled_categories=invalid)

    def test_generic_token_heuristic_ignores_word_like_identifiers(self):
        identifiers = (
            "cpbin-safe-live-service-92741",
            "cpbin-service-integrity-63814",
            "order-confirmation-2026-09-18",
            "backup-report-123456",
            "project-alpha-stage-2",
        )
        for identifier in identifiers:
            with self.subTest(identifier=identifier):
                self.assertNotIn(Category.TOKEN, self.categories(identifier))

    def test_generic_token_heuristic_preserves_secret_like_values(self):
        cases = (
            "A7f9K2mQ8xR4vN6pT3zW5cY1",
            "QWxhZGRpbjpPcGVuU2VzYW1lMTIzNDU2PQ==",
            "9f4a7c2e8b1d6a3f0c5e9b7d4a2c8f1e",
            "aB7f9-K2mQ8_xR4vN6pT3zW5cY1",
            "sk-abcdefghijklmnopqrstuv",
        )
        for value in cases:
            with self.subTest(value=value):
                result = analyze_text(value)
                self.assertIn(
                    Category.OPENAI_API_KEY if value.startswith("sk-") else Category.TOKEN,
                    self.categories(value),
                )
                self.assertEqual(RiskLevel.HIGH, result.highest_risk)

    def test_secretlike_word_identifiers_remain_tokens(self):
        cases = (
            "api-token-prod-12345678901234567890",
            "secret-key-stage-12345678901234567890",
            "access-token-prod-98765432109876543210",
            "auth-token-user-12345678901234567890",
        )
        for value in cases:
            with self.subTest(value=value):
                result = analyze_text(value)
                self.assertIn(Category.TOKEN, self.categories(value))
                self.assertEqual(RiskLevel.HIGH, result.highest_risk)

    def test_contextual_secret_rules_remain_independent_of_generic_token(self):
        bearer = analyze_text(
            "Authorization: Bearer A7f9K2mQ8xR4vN6pT3zW5cY1"
        )
        assignment = analyze_text(
            "access_token=A7f9K2mQ8xR4vN6pT3zW5cY1"
        )
        self.assertIn(
            Category.AUTHORIZATION,
            [item.category for item in bearer.detections],
        )
        self.assertIn(
            Category.SECRET_ASSIGNMENT,
            [item.category for item in assignment.detections],
        )
        self.assertEqual(RiskLevel.HIGH, bearer.highest_risk)
        self.assertEqual(RiskLevel.HIGH, assignment.highest_risk)

    def test_live_test_money_and_secret_assignment_regressions(self):
        money = analyze_text("1234 PLN")
        secret = analyze_text("password=CPBIN_SYNTHETIC_ONLY_92741")
        self.assertEqual(
            [Category.MONEY_AMOUNT_PLN_USD],
            [item.category for item in money.detections],
        )
        self.assertEqual(RiskLevel.LOW, money.highest_risk)
        self.assertIn(
            Category.SECRET_ASSIGNMENT,
            [item.category for item in secret.detections],
        )
        self.assertEqual(RiskLevel.HIGH, secret.highest_risk)

    def test_high_risk_wins_overlap_and_redaction_is_stable(self):
        text = "password=person@example.com and person@example.com"
        first = analyze_text(text)
        second = analyze_text(text)
        self.assertEqual(first, second)
        self.assertEqual(RiskLevel.HIGH, first.highest_risk)
        self.assertNotIn("person@example.com", first.redacted_text)

    def test_repeated_value_uses_same_marker(self):
        result = analyze_text("person@example.com person@example.com")
        self.assertEqual(2, result.redacted_text.count("[EMAIL_1]"))

    def test_possible_seed_structure_is_high_risk(self):
        words = "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima"
        result = analyze_text(words)
        self.assertIn(Category.POSSIBLE_SEED_PHRASE, self.categories(words))
        self.assertEqual(RiskLevel.CRITICAL, result.highest_risk)

    def test_bip39_resource_integrity(self):
        data = files("copypastebin.data").joinpath("bip39_english.txt").read_bytes()
        words = load_bip39_words()
        self.assertEqual(BIP39_RESOURCE_SHA256, sha256(data).hexdigest())
        self.assertEqual(2048, len(words))
        self.assertEqual(2048, len(set(words)))
        self.assertEqual(tuple(sorted(words)), words)

    def test_confirmed_bip39_vector_is_high_risk_and_fully_redacted(self):
        phrase = " ".join(["abandon"] * 11 + ["about"])
        result = analyze_text(phrase)
        self.assertEqual(1, len(result.detections))
        self.assertEqual("bip39-confirmed-v1", result.detections[0].rule_id)
        self.assertFalse(result.detections[0].heuristic)
        self.assertEqual(RiskLevel.CRITICAL, result.highest_risk)
        self.assertEqual("[POSSIBLE_SEED_PHRASE_1]", result.redacted_text)

    def test_bip39_words_with_invalid_checksum_remain_high_risk(self):
        phrase = " ".join(["abandon"] * 11 + ["ability"])
        result = analyze_text(phrase)
        self.assertEqual("possible-bip39-invalid-checksum-v1", result.detections[0].rule_id)
        self.assertTrue(result.detections[0].heuristic)
        self.assertEqual(RiskLevel.CRITICAL, result.highest_risk)

    def test_bip39_resource_mismatch_fails_closed(self):
        load_bip39_words.cache_clear()
        try:
            with patch("copypastebin.detection.BIP39_RESOURCE_SHA256", "0" * 64):
                with self.assertRaises(Bip39ResourceError):
                    analyze_text("ordinary text")
        finally:
            load_bip39_words.cache_clear()
