"""Bounded official filing documents, targeted items and linked EX-99 earnings exhibits."""
from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlsplit

from app.models.outlook_document import SourceTable


class FilingText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.links = [], []
        self.hidden = 0
        self.anchor = None
        self.rows = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag in ("script", "style", "ix:header"):
            self.hidden += 1
        if self.hidden:
            return
        if tag == "tr":
            self.rows.append({"text": [], "links": []})
        if tag in ("p", "div", "br", "tr", "td", "th", "li"):
            self.parts.append("\n")
        if tag == "a":
            self.anchor = [attributes.get("href", ""), ""]

    def handle_endtag(self, tag):
        if tag in ("script", "style", "ix:header"):
            self.hidden = max(0, self.hidden-1)
        if not self.hidden and tag in ("p", "div", "tr", "td", "th", "li"):
            self.parts.append("\n")
        if tag == "a" and self.anchor is not None:
            self.links.append(tuple(self.anchor))
            if self.rows:
                self.rows[-1]["links"].append(tuple(self.anchor))
            self.anchor = None
        if tag == "tr" and self.rows:
            row = self.rows.pop()
            label = " ".join(" ".join(row["text"]).split())
            # Some filers put 99.1 in a separate cell and link only the description.
            if re.match(r"^(?:Exhibit )?99\.(?:1|01)\s", label, re.I):
                # Preserve every candidate; resolution validates and deduplicates destinations.
                self.links.extend((href, "99.1") for href, _ in row["links"])

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)
            if self.rows:
                self.rows[-1]["text"].append(data)
            if self.anchor is not None:
                self.anchor[1] += data

    @property
    def text(self):
        return "\n".join(line for part in "".join(self.parts).splitlines()
                         if (line := re.sub(r"\s+", " ", part).strip()))


def parse_filing(html):
    parser = FilingText()
    parser.feed(html)
    tables = BoundedTables()
    tables.feed(html)
    parser.tables = tuple(tables.tables)
    return parser


def item_text(text, item):
    """Reject missing/repeated item boundaries (e.g. table of contents)."""
    headings = list(re.finditer(r"\bItem\s+(\d\.\d{2})\b", text, re.I))
    targets = [index for index, match in enumerate(headings) if match[1] == item]
    if len(targets) != 1:
        return ""
    index = targets[0]
    end = headings[index+1].start() if index+1 < len(headings) else len(text)
    return bounded_text(text[headings[index].end():end], 15000)


def bounded_text(text, limit):
    # Do not turn a truncated conditional assertion into a complete supported sentence.
    return text if len(text) <= limit else text[:limit].rsplit("\n", 1)[0] if "\n" in text[:limit] else ""


def earnings_exhibit_url(primary_url, links):
    """Follow one explicitly numbered exhibit in this exact SEC accession directory."""
    base = primary_url.rsplit("/", 1)[0] + "/"
    destinations = set()
    for href, label in links:
        if not re.fullmatch(r"(?:Exhibit\s+)?99(?:\.1|\.01)?", label.strip(), re.I):
            continue
        url = urljoin(primary_url, href)
        parts = urlsplit(url)
        if (url.startswith(base) and parts.scheme == "https" and parts.hostname == "www.sec.gov"
                and not parts.query and not parts.fragment
                and re.fullmatch(r"[A-Za-z0-9_.-]+\.(?:htm|html|txt)", url[len(base):], re.I)
                and url != primary_url):
            destinations.add(url)
    return next(iter(destinations)) if len(destinations) == 1 else None


class BoundedTables(HTMLParser):
    """Retain only complete small non-nested tables; no rowspan reconstruction."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.depth = 0
        self.rows = []
        self.row = None
        self.cell = None
        self.invalid = False

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.depth += 1
            if self.depth == 1:
                self.rows, self.row, self.cell = [], None, None
                self.invalid = len(self.tables) >= 8
            else:
                self.invalid = True
        if self.depth != 1 or self.invalid:
            return
        if tag in ("script", "style", "ix:header"):
            self.invalid = True
        elif tag == "tr":
            if self.row is not None or len(self.rows) >= 40:
                self.invalid = True
            self.row = []
        elif tag in ("td", "th"):
            attrs = dict(attrs)
            if self.row is None or self.cell is not None or len(self.row) >= 24:
                self.invalid = True
                return
            try:
                span = int(attrs.get("colspan", "1"))
                if not 1 <= span <= 24 or int(attrs.get("rowspan", "1")) != 1:
                    self.invalid = True
                self.cell = {"text": "", "colspan": span}
            except (TypeError, ValueError):
                self.invalid = True

    def handle_data(self, data):
        if self.depth == 1 and not self.invalid and self.cell is not None:
            if len(self.cell["text"]) + len(data) > 500:
                self.invalid = True
            else:
                self.cell["text"] += data

    def handle_endtag(self, tag):
        if self.depth == 1 and not self.invalid:
            if tag in ("td", "th"):
                if self.cell is None or self.row is None:
                    self.invalid = True
                else:
                    self.cell["text"] = " ".join(self.cell["text"].split())
                    self.row.append(self.cell)
                    self.cell = None
            elif tag == "tr":
                if self.row is None or self.cell is not None:
                    self.invalid = True
                else:
                    self.rows.append(self.row)
                    self.row = None
            elif tag == "table" and self.row is None and self.cell is None:
                self.tables.append(SourceTable(rows=tuple(tuple(row) for row in self.rows)))
        if tag == "table":
            self.depth = max(0, self.depth-1)
