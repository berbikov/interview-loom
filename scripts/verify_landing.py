import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

PLACEHOLDER_PATTERN = re.compile(r"\{\{[A-Z_]+\}\}")


class AssetReferenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        relevant_attribute = "src" if tag in {"img", "script"} else "href"
        for name, value in attrs:
            if name == relevant_attribute and value:
                self.references.append(value)


def verify_landing(output_dir: Path) -> list[str]:
    resolved_output_dir = output_dir.resolve()
    errors: list[str] = []
    html_files = sorted(resolved_output_dir.glob("*.html"))
    if not html_files:
        return ["В собранном лендинге нет HTML-файлов."]

    for html_file in html_files:
        content = html_file.read_text(encoding="utf-8")
        if PLACEHOLDER_PATTERN.search(content):
            errors.append(f"{html_file.name}: остался шаблонный placeholder")
        parser = AssetReferenceParser()
        parser.feed(content)
        for reference in parser.references:
            parsed_reference = urlsplit(reference)
            if parsed_reference.scheme or parsed_reference.netloc:
                continue
            if reference.startswith("#"):
                continue
            if parsed_reference.path.startswith("/"):
                errors.append(
                    f"{html_file.name}: абсолютный путь {reference!r} ломает GitHub Pages subpath"
                )
                continue
            target = (html_file.parent / parsed_reference.path).resolve()
            if resolved_output_dir not in target.parents and target != resolved_output_dir:
                errors.append(f"{html_file.name}: путь выходит за каталог сайта: {reference!r}")
            elif not target.exists():
                errors.append(f"{html_file.name}: не найден файл {reference!r}")
    return errors


def main() -> None:
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("public")
    errors = verify_landing(output_dir)
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Landing verified: {output_dir}")


if __name__ == "__main__":
    main()
