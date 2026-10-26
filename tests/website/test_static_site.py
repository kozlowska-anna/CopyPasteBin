from __future__ import annotations

import json
import re
import unittest
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "website"
PAGES = (SITE / "index.html", SITE / "en" / "index.html")
EXPECTED_CANONICALS = {
    "pl": "https://kozlowska-anna.github.io/CopyPasteBin/",
    "en": "https://kozlowska-anna.github.io/CopyPasteBin/en/",
}
EXPECTED_METADATA = {
    "pl": {
        "title": "CopyPasteBin | Menedżer schowka dla GNOME",
        "h1": "Sprawdź, zanim wkleisz.",
        "description": (
            "CopyPasteBin to menedżer schowka dla GNOME, który wykrywa dane "
            "wrażliwe, ostrzega przed wklejeniem i umożliwia lokalną anonimizację "
            "tekstu i obrazów."
        ),
    },
    "en": {
        "title": "CopyPasteBin | Clipboard Manager for GNOME",
        "h1": "Check Before You Paste.",
        "description": (
            "CopyPasteBin is a clipboard manager for GNOME with sensitive-data "
            "detection, paste warnings, text and image redaction, and a built-in paste editor."
        ),
    },
}
EXPECTED_COMPATIBILITY = {
    "pl": (
        "Wymagane środowisko.",
        "Przykład zgodnej dystrybucji:",
        "Ubuntu 26.04 LTS (GNOME 50, Wayland)",
        "Obecnie nieobsługiwane środowiska: KDE Plasma, Cinnamon, Xfce oraz sesje X11.",
        "Zgodność zależy od środowiska graficznego i jego wersji, a nie wyłącznie od nazwy dystrybucji.",
    ),
    "en": (
        "Required environment.",
        "Example of a compatible Linux distribution:",
        "Ubuntu 26.04 LTS (GNOME 50, Wayland)",
        "Currently unsupported: KDE Plasma, Cinnamon, Xfce, and X11 sessions.",
        "Compatibility depends on the desktop environment and its version, not just the Linux distribution.",
    ),
}


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.html_lang = ""
        self.ids: list[str] = []
        self.h1_count = 0
        self.h1_text = ""
        self.in_h1 = False
        self.title = ""
        self.in_title = False
        self.links: list[dict[str, str]] = []
        self.metas: list[dict[str, str]] = []
        self.resources: list[str] = []
        self.buttons: list[dict[str, str]] = []
        self.images: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {key: value or "" for key, value in attrs}
        if tag == "html":
            self.html_lang = data.get("lang", "")
        if "id" in data:
            self.ids.append(data["id"])
        if tag == "h1":
            self.h1_count += 1
            self.in_h1 = True
        if tag == "title":
            self.in_title = True
        if tag in {"a", "link"}:
            self.links.append(data)
        if tag == "meta":
            self.metas.append(data)
        if tag == "button":
            self.buttons.append(data)
        if tag == "img":
            self.images.append(data)
        if tag in {"img", "script"} and data.get("src"):
            self.resources.append(data["src"])
        if tag == "link" and data.get("rel") in {"stylesheet", "icon"} and data.get("href"):
            self.resources.append(data["href"])

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        if tag == "h1":
            self.in_h1 = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title += data
        if self.in_h1:
            self.h1_text += data


def parse_page(path: Path) -> PageParser:
    parser = PageParser()
    parser.feed(path.read_text(encoding="utf-8"))
    parser.close()
    return parser


def meta_content(parser: PageParser, *, name: str | None = None, prop: str | None = None) -> str:
    for meta in parser.metas:
        if name and meta.get("name") == name:
            return meta.get("content", "")
        if prop and meta.get("property") == prop:
            return meta.get("content", "")
    return ""


class StaticSiteTests(unittest.TestCase):
    def test_required_public_files_exist(self) -> None:
        for relative in ("index.html", "en/index.html", "robots.txt", "sitemap.xml", ".nojekyll"):
            self.assertTrue((SITE / relative).is_file(), relative)

    def test_pages_have_valid_structure_and_unique_ids(self) -> None:
        for page in PAGES:
            with self.subTest(page=page.relative_to(SITE)):
                parser = parse_page(page)
                self.assertIn(parser.html_lang, EXPECTED_CANONICALS)
                self.assertEqual(parser.h1_count, 1)
                self.assertTrue(10 <= len(parser.title.strip()) <= 65)
                self.assertEqual(len(parser.ids), len(set(parser.ids)))
                self.assertTrue(any(link.get("href") == "#main" for link in parser.links))
                self.assertTrue(all(button.get("type") == "button" for button in parser.buttons))

    def test_seo_metadata_is_complete_and_language_specific(self) -> None:
        titles: set[str] = set()
        descriptions: set[str] = set()
        for page in PAGES:
            parser = parse_page(page)
            lang = parser.html_lang
            canonical = next(
                link.get("href", "")
                for link in parser.links
                if link.get("rel") == "canonical"
            ) if any(link.get("rel") == "canonical" for link in parser.links) else ""
            alternatives = {
                link.get("hreflang"): link.get("href")
                for link in parser.links
                if link.get("rel") == "alternate"
            }
            description = meta_content(parser, name="description")
            expected = EXPECTED_METADATA[lang]
            self.assertEqual(canonical, EXPECTED_CANONICALS[lang])
            self.assertEqual(alternatives.get("pl"), EXPECTED_CANONICALS["pl"])
            self.assertEqual(alternatives.get("en"), EXPECTED_CANONICALS["en"])
            self.assertEqual(alternatives.get("x-default"), EXPECTED_CANONICALS["pl"])
            self.assertEqual(parser.title.strip(), expected["title"])
            self.assertEqual(parser.h1_text.strip(), expected["h1"])
            self.assertEqual(description, expected["description"])
            self.assertTrue(80 <= len(description) <= 180)
            self.assertEqual(meta_content(parser, prop="og:url"), canonical)
            self.assertEqual(meta_content(parser, prop="og:site_name"), "CopyPasteBin")
            self.assertEqual(meta_content(parser, prop="og:title"), expected["title"])
            self.assertEqual(meta_content(parser, prop="og:description"), expected["description"])
            self.assertTrue(meta_content(parser, prop="og:image").startswith("https://"))
            self.assertTrue(meta_content(parser, prop="og:image").endswith("share-card-1.1.png"))
            self.assertEqual(meta_content(parser, name="twitter:image"), meta_content(parser, prop="og:image"))
            titles.add(parser.title.strip())
            descriptions.add(description)
        self.assertEqual(len(titles), len(PAGES))
        self.assertEqual(len(descriptions), len(PAGES))

    def test_software_application_structured_data_is_factual_and_bilingual(self) -> None:
        for page in PAGES:
            parser = parse_page(page)
            source = page.read_text(encoding="utf-8")
            match = re.search(
                r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
                source,
                flags=re.DOTALL,
            )
            self.assertIsNotNone(match, page)
            data = json.loads(match.group(1))
            lang = parser.html_lang
            self.assertEqual(data["@context"], "https://schema.org")
            self.assertEqual(data["@type"], "SoftwareApplication")
            self.assertEqual(data["name"], "CopyPasteBin")
            self.assertEqual(data["softwareVersion"], "1.1")
            self.assertEqual(data["applicationCategory"], "SecurityApplication")
            self.assertEqual(data["mainEntityOfPage"], EXPECTED_CANONICALS[lang])
            self.assertEqual(data["description"], EXPECTED_METADATA[lang]["description"])
            self.assertEqual(data["offers"]["price"], 0)
            self.assertTrue(data["isAccessibleForFree"])
            self.assertEqual(len(data["downloadUrl"]), 2)
            self.assertGreaterEqual(len(data["featureList"]), 4)
            self.assertNotIn("aggregateRating", data)
            self.assertNotIn("review", data)

    def test_all_local_links_and_resources_resolve(self) -> None:
        for page in PAGES:
            parser = parse_page(page)
            candidates = [link.get("href", "") for link in parser.links] + parser.resources
            for raw in candidates:
                with self.subTest(page=page.relative_to(SITE), target=raw):
                    if not raw or raw.startswith(("#", "https://", "mailto:", "tel:")):
                        continue
                    target = (page.parent / raw.split("#", 1)[0].split("?", 1)[0]).resolve()
                    self.assertTrue(target.is_relative_to(SITE.resolve()))
                    self.assertTrue(target.exists(), target)

    def test_repository_documents_linked_from_site_exist(self) -> None:
        prefix = "https://github.com/kozlowska-anna/CopyPasteBin/blob/main/"
        for page in PAGES:
            for link in parse_page(page).links:
                href = link.get("href", "")
                if not href.startswith(prefix):
                    continue
                target = ROOT / href.removeprefix(prefix)
                with self.subTest(page=page.relative_to(SITE), target=target.relative_to(ROOT)):
                    self.assertTrue(target.is_file(), target)

    def test_internal_fragments_resolve(self) -> None:
        for page in PAGES:
            parser = parse_page(page)
            ids = set(parser.ids)
            for link in parser.links:
                href = link.get("href", "")
                if href.startswith("#"):
                    self.assertIn(href[1:], ids, (page, href))

    def test_images_are_accessible_and_dimensioned(self) -> None:
        for page in PAGES:
            for image in parse_page(page).images:
                with self.subTest(page=page.relative_to(SITE), src=image.get("src")):
                    self.assertIn("alt", image)
                    if not image.get("src"):
                        continue
                    self.assertTrue(image.get("width"))
                    self.assertTrue(image.get("height"))

    def test_runtime_resources_are_local(self) -> None:
        for page in PAGES:
            parser = parse_page(page)
            for resource in parser.resources:
                self.assertFalse(urlparse(resource).scheme, (page, resource))

    def test_language_switch_is_bidirectional(self) -> None:
        polish = parse_page(SITE / "index.html")
        english = parse_page(SITE / "en" / "index.html")
        self.assertTrue(any(link.get("hreflang") == "en" and link.get("href") == "en/" for link in polish.links))
        self.assertTrue(any(link.get("hreflang") == "pl" and link.get("href") == "../" for link in english.links))

    def test_distribution_examples_are_bilingual(self) -> None:
        for page in PAGES:
            parser = parse_page(page)
            source = page.read_text(encoding="utf-8")
            for expected_text in EXPECTED_COMPATIBILITY[parser.html_lang]:
                with self.subTest(page=page.relative_to(SITE), text=expected_text):
                    self.assertIn(expected_text, source)

    def test_version_1_1_release_is_described_consistently(self) -> None:
        expected_by_language = {
            "pl": (
                "Wydanie · 1.1",
                "Anonimizacja obrazów",
                "Dwa instalatory z tego samego kodu",
                "Pakiet DEB",
                "Archiwum tar.gz",
                "copypastebin_1.1-1_all.deb",
                "CopyPasteBin-linux-1.1.tar.gz",
                "releases/download/v1.1/copypastebin_1.1-1_all.deb",
                "releases/download/v1.1/CopyPasteBin-linux-1.1.tar.gz",
                "releases/download/v1.1/SHA256SUMS",
                "sha256sum --check --ignore-missing SHA256SUMS",
                "Watch → Custom → Releases",
                "Oba warianty instalacji sprawdzono w docelowym środowisku GNOME/Wayland",
                "Aktualizacja pakietu DEB wymaga obecnie pobrania nowej wersji i zainstalowania jej przez APT",
            ),
            "en": (
                "Release · 1.1",
                "Image redaction",
                "Two installers from the same source",
                "DEB package",
                "tar.gz archive",
                "copypastebin_1.1-1_all.deb",
                "CopyPasteBin-linux-1.1.tar.gz",
                "releases/download/v1.1/copypastebin_1.1-1_all.deb",
                "releases/download/v1.1/CopyPasteBin-linux-1.1.tar.gz",
                "releases/download/v1.1/SHA256SUMS",
                "sha256sum --check --ignore-missing SHA256SUMS",
                "Watch → Custom → Releases",
                "Both installation variants were checked in the target GNOME/Wayland environment",
                "Updating the DEB package currently requires downloading the new version and installing it through APT",
            ),
        }
        for page in PAGES:
            parser = parse_page(page)
            source = page.read_text(encoding="utf-8")
            for expected_text in expected_by_language[parser.html_lang]:
                with self.subTest(page=page.relative_to(SITE), text=expected_text):
                    self.assertIn(expected_text, source)
            self.assertNotIn("Kandydat do wydania", source)
            self.assertNotIn("Release candidate", source)
            self.assertNotIn("pozostaje nieopublikowana", source)
            self.assertNotIn("remains unpublished", source)
            self.assertNotIn("Pobierz stabilne 1.0.0", source)
            self.assertNotIn("Download stable 1.0.0", source)
            self.assertNotIn("26/26", source)

    def test_public_roadmap_separates_commitments_from_exploration(self) -> None:
        expected_by_language = {
            "pl": (
                'id="roadmapa"',
                "Co dalej z CopyPasteBin.",
                "Planowane",
                "Wygodniejsze przygotowanie treści",
                "Więcej sposobów ochrony",
                "Badamy",
                "Wersja 1.1 pozwala ręcznie zakrywać fragmenty obrazów",
                "/ROADMAP.pl.md",
            ),
            "en": (
                'id="roadmap"',
                "What’s next for CopyPasteBin.",
                "Planned",
                "Easier content preparation",
                "More ways to protect content",
                "Exploring",
                "Version 1.1 lets you manually cover parts of images",
                "/ROADMAP.md",
            ),
        }
        for page in PAGES:
            parser = parse_page(page)
            source = page.read_text(encoding="utf-8")
            for expected_text in expected_by_language[parser.html_lang]:
                with self.subTest(page=page.relative_to(SITE), text=expected_text):
                    self.assertIn(expected_text, source)
            self.assertNotIn("wyrażenia regularne", source)
            self.assertNotIn("regular expressions", source)
            self.assertNotIn("Domknięcie wersji 1.1", source)
            self.assertNotIn("Finalize version 1.1", source)

    def test_product_positioning_and_privacy_summary_are_bilingual(self) -> None:
        expected_by_language = {
            "pl": (
                "Privacy-focused Clipboard Manager",
                "Menedżer, ale nie klasyczne archiwum schowka.",
                "ochrona przed niefortunnym kliknięciem",
                "Lokalnie, bez konta i chmury.",
            ),
            "en": (
                "Privacy-focused Clipboard Manager",
                "not a traditional clipboard archive",
                "built-in paste editor",
                "Local, with no account or cloud.",
            ),
        }
        for page in PAGES:
            parser = parse_page(page)
            source = page.read_text(encoding="utf-8")
            self.assertIn('class="product-positioning"', source)
            for expected_text in expected_by_language[parser.html_lang]:
                with self.subTest(page=page.relative_to(SITE), text=expected_text):
                    self.assertIn(expected_text, source)

    def test_use_cases_present_four_concrete_bilingual_situations(self) -> None:
        expected_by_language = {
            "pl": (
                'id="zastosowania"',
                'href="#zastosowania">Zastosowania</a>',
                "Kiedy może się przydać CopyPasteBin?",
                "Gdy piszesz wiadomość",
                "Gdy pracujesz z kodem lub terminalem",
                "Gdy korzystasz z narzędzia AI",
                "sprawdź kopiowany fragment dokumentu",
                "Gdy udostępniasz obraz",
            ),
            "en": (
                'id="use-cases"',
                'href="#use-cases">Use cases</a>',
                "When might CopyPasteBin help?",
                "When writing a message",
                "When working with code or a terminal",
                "When using an AI tool",
                "review copied text from a document",
                "When sharing an image",
            ),
        }
        for page in PAGES:
            parser = parse_page(page)
            source = page.read_text(encoding="utf-8")
            for expected_text in expected_by_language[parser.html_lang]:
                with self.subTest(page=page.relative_to(SITE), text=expected_text):
                    self.assertIn(expected_text, source)
            section_id = "zastosowania" if parser.html_lang == "pl" else "use-cases"
            section = re.search(
                rf'<section[^>]+id="{section_id}"[^>]*>(?P<body>.*?)</section>',
                source,
                re.DOTALL,
            )
            self.assertIsNotNone(section)
            body = section.group("body")
            self.assertIn('class="use-case-list"', body)
            self.assertEqual(body.count("<li>"), 4)
            self.assertNotIn("trust-strip", body)
            self.assertNotIn("trust-item", body)

    def test_clipboard_editor_is_presented_as_a_general_text_tool(self) -> None:
        expected_by_language = {
            "pl": ("Podręczny edytor treści", "wprowadź ręczne poprawki", "dopiero po Twojej akceptacji"),
            "en": ("Handy text editor", "make manual changes", "only after your confirmation"),
        }
        for page in PAGES:
            parser = parse_page(page)
            source = page.read_text(encoding="utf-8")
            for expected_text in expected_by_language[parser.html_lang]:
                with self.subTest(page=page.relative_to(SITE), text=expected_text):
                    self.assertIn(expected_text, source)

    def test_features_lead_with_the_owner_priorities(self) -> None:
        expected_by_language = {
            "pl": (
                "Podręczny edytor treści",
                "Anonimizacja obrazów",
                "Reguły i dokładne wykluczenia",
                "Historia ostatnich 15 kopiowań",
                "Cztery poziomy ryzyka",
            ),
            "en": (
                "Handy text editor",
                "Image redaction",
                "Rules and exact exceptions",
                "15-item clipboard history",
                "Four risk levels",
            ),
        }
        for page in PAGES:
            parser = parse_page(page)
            source = page.read_text(encoding="utf-8")
            section_id = "mozliwosci" if parser.html_lang == "pl" else "features"
            section = re.search(
                rf'<section[^>]+id="{section_id}"[^>]*>(?P<body>.*?)</section>',
                source,
                re.DOTALL,
            )
            self.assertIsNotNone(section)
            body = section.group("body")
            positions = [body.index(text) for text in expected_by_language[parser.html_lang]]
            self.assertEqual(positions, sorted(positions), page)

    def test_gallery_contains_full_uncropped_screenshot_set(self) -> None:
        expected_by_language = {
            "pl": {
                "01-copypastebin-1-1-menu-menedzera-schowka-gnome-PL.png",
                "02-copypastebin-1-1-ostrzezenie-przed-wklejeniem-danych-wrazliwych-PL.png",
                "03-copypastebin-1-1-edytor-schowka-podswietlanie-danych-wrazliwych-PL.png",
                "04-copypastebin-1-1-selektywna-anonimizacja-narzedzia-edycji-PL.png",
                "05-copypastebin-1-1-reguly-wlasne-dokladne-wykluczenia-PL.png",
                "06-copypastebin-1-1-lokalny-edytor-anonimizacji-obrazow-PL.png",
                "07-copypastebin-1-1-tymczasowa-historia-schowka-PL.png",
            },
            "en": {
                "01-copypastebin-1-1-clipboard-manager-menu-gnome-EN.png",
                "02-copypastebin-1-1-sensitive-data-paste-warning-EN.png",
                "03-copypastebin-1-1-clipboard-editor-risk-highlighting-EN.png",
                "04-copypastebin-1-1-selective-anonymization-editing-tools-EN.png",
                "05-copypastebin-1-1-custom-rules-exact-exceptions-EN.png",
                "06-copypastebin-1-1-local-image-redaction-editor-EN.png",
                "07-copypastebin-1-1-session-only-clipboard-history-EN.png",
            },
        }
        for page in PAGES:
            parser = parse_page(page)
            sources = {
                Path(image.get("src", "")).name
                for image in parser.images
            }
            self.assertTrue(expected_by_language[parser.html_lang].issubset(sources), page)

        css = (SITE / "assets" / "css" / "styles.css").read_text(encoding="utf-8")
        gallery_rule = re.search(r"\.gallery-button img\s*\{(?P<body>[^}]*)\}", css, re.DOTALL)
        self.assertIsNotNone(gallery_rule)
        body = gallery_rule.group("body")
        self.assertIn("width: auto", body)
        self.assertIn("height: auto", body)
        self.assertIn("object-fit: contain", body)
        self.assertNotIn("aspect-ratio", body)
        self.assertNotIn("object-fit: cover", body)

    def test_page_uses_plain_white_section_backgrounds(self) -> None:
        css = (SITE / "assets" / "css" / "styles.css").read_text(encoding="utf-8").lower()
        self.assertNotIn("gradient(", css)
        for selector in ("body", ".site-header", ".hero", ".section-soft", ".section-dark", ".cta"):
            with self.subTest(selector=selector):
                rule = re.search(rf"{re.escape(selector)}\s*\{{(?P<body>[^}}]*)\}}", css, re.DOTALL)
                self.assertIsNotNone(rule)
                self.assertRegex(rule.group("body"), r"background:\s*(?:#fff|var\(--paper\));")

    def test_site_palette_uses_one_cyan_accent_without_green(self) -> None:
        css = (SITE / "assets" / "css" / "styles.css").read_text(encoding="utf-8").lower()
        for token in (
            "--ink: #14243a",
            "--cyan: #0f789f",
            "--cyan-dark: #075d7d",
            "--line: #d6e2f0",
        ):
            self.assertIn(token, css)
        self.assertNotIn("--green", css)
        self.assertNotIn("--blue", css)
        self.assertNotIn("--violet", css)
        self.assertNotIn("#178143", css)
        self.assertNotIn("#0f6833", css)
        primary = re.search(r"\.button-primary\s*\{(?P<body>[^}]*)\}", css, re.DOTALL)
        self.assertIsNotNone(primary)
        self.assertIn("background: var(--cyan)", primary.group("body"))

    def test_hero_arranges_all_four_product_risk_banners(self) -> None:
        expected = {
            "risk-low": "#245f9e",
            "risk-medium": "#8a5a00",
            "risk-high": "#a61b29",
            "risk-critical": "#67101b",
        }
        css = (SITE / "assets" / "css" / "styles.css").read_text(encoding="utf-8").lower()
        for page in PAGES:
            source = page.read_text(encoding="utf-8")
            self.assertNotIn("HMAC", source)
            self.assertGreaterEqual(source.lower().count("open source"), 2, page)
            self.assertEqual(source.count('class="project-credit"'), 2, page)
            self.assertIn("ChatGPT", source)
            self.assertIn("Codex", source)
            self.assertIn("OpenAI", source)
            self.assertLess(source.index("ChatGPT"), source.index("GPL-3.0-or-later", source.index("ChatGPT")), page)
            self.assertIn('href="#jak-dziala"' if page == SITE / "index.html" else 'href="#how-it-works"', source)
            for class_name in expected:
                self.assertEqual(source.count(f"risk-banner {class_name}"), 1, (page, class_name))
            self.assertNotIn("home path", source.lower())
            self.assertNotIn("ścieżka domowa", source.lower())
            self.assertNotIn("seed phrase", source.lower())
            self.assertNotIn("fraza seed", source.lower())
            self.assertNotIn("GitHub Pages documentation", source)
            self.assertNotIn("Bez udawania, że ryzyko znika", source)
            self.assertNotIn("Without pretending risk disappears", source)
            self.assertNotIn('name="keywords"', source.lower())
            self.assertIn("styles.css?v=20261026-3", source)
            self.assertIn("site.js?v=20261019-6", source)
        stack_rule = re.search(r"\.risk-stack\s*\{(?P<body>[^}]*)\}", css, re.DOTALL)
        banner_rule = re.search(r"\.risk-banner\s*\{(?P<body>[^}]*)\}", css, re.DOTALL)
        self.assertIsNotNone(stack_rule)
        self.assertIsNotNone(banner_rule)
        self.assertIn("position: relative", stack_rule.group("body"))
        self.assertIn("position: absolute", banner_rule.group("body"))
        brand_rule = re.search(r"\.brand img\s*\{(?P<body>[^}]*)\}", css, re.DOTALL)
        self.assertIsNotNone(brand_rule)
        self.assertIn("width: 3.25rem", brand_rule.group("body"))
        self.assertIn("height: 3.25rem", brand_rule.group("body"))
        card_rule = re.search(
            r"\.system-card,\s*\.download-card\s*\{(?P<body>[^}]*)\}",
            css,
            re.DOTALL,
        )
        self.assertIsNotNone(card_rule)
        self.assertIn("min-width: 0", card_rule.group("body"))
        for class_name, color in expected.items():
            rule = re.search(rf"\.{class_name}\s*\{{(?P<body>[^}}]*)\}}", css, re.DOTALL)
            self.assertIsNotNone(rule)
            self.assertIn(f"background: {color}", rule.group("body"))

    def test_visible_brand_uses_web_svg_with_dark_navy_contour(self) -> None:
        css = (SITE / "assets" / "css" / "styles.css").read_text(encoding="utf-8").lower()
        app_logo = SITE / "assets" / "images" / "logo.svg"
        web_logo = SITE / "assets" / "images" / "logo-web.svg"
        share_card = SITE / "assets" / "images" / "share-card-1.1.png"
        self.assertTrue(app_logo.is_file())
        self.assertTrue(web_logo.is_file())
        self.assertTrue(share_card.is_file())
        self.assertGreater(share_card.stat().st_size, 10_000)
        ET.parse(app_logo)
        ET.parse(web_logo)
        web_logo_source = web_logo.read_text(encoding="utf-8").lower()
        self.assertGreaterEqual(web_logo_source.count('stroke="#071d35"'), 2)
        for color in ("#50c8ff", "#ffd12e", "#ff5a69", "#c92f52"):
            self.assertIn(color, web_logo_source)
        for page in PAGES:
            source = page.read_text(encoding="utf-8")
            self.assertNotIn('logo.png"', source)
            self.assertEqual(source.count("logo-web.svg"), 3, page)
        self.assertGreaterEqual(css.count("drop-shadow(0 0 1px #061827)"), 2)

    def test_sitemap_and_robots_match_public_urls(self) -> None:
        sitemap = ET.parse(SITE / "sitemap.xml")
        namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locations = {node.text for node in sitemap.findall("s:url/s:loc", namespace)}
        self.assertEqual(locations, set(EXPECTED_CANONICALS.values()))
        robots = (SITE / "robots.txt").read_text(encoding="utf-8")
        self.assertIn("Allow: /", robots)
        self.assertIn("https://kozlowska-anna.github.io/CopyPasteBin/sitemap.xml", robots)

    def test_publish_tree_contains_no_symlinks_or_obvious_private_paths(self) -> None:
        files = [path for path in SITE.rglob("*") if path.is_file()]
        self.assertTrue(files)
        self.assertFalse(any(path.is_symlink() for path in SITE.rglob("*")))
        text = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in files
            if path.suffix in {".html", ".css", ".js", ".txt", ".xml"}
        )
        self.assertNotRegex(text, re.compile(r"/home/(?!example(?:/|\b))[^\s<]+"))
        self.assertNotIn("BEGIN PRIVATE KEY", text)
        self.assertNotIn("github_pat_", text)


if __name__ == "__main__":
    unittest.main()
