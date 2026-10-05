"""Bounded official Fed calendar/statement adapter. No news or inferred expectations."""
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction
from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

from app.models.outlook_document import SourceDocument
from app.models.outlook_event import ExternalEvent, EventScope, EventSource, EventValue
from .transport import Cache, JsonClient, ProviderUnavailable

CALENDAR_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
ET = ZoneInfo("America/New_York")
RECENT_DAYS = 90
MAX_RECENT = 2
MAX_UPCOMING = 2
NUMBER = r"(?:\d+-\d+/\d+|\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)"
MONTHS = {name.lower(): index for index, name in enumerate(
    ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"), 1)}


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.links, self.skip = [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag == "a":
            self.links.append(dict(attrs).get("href", ""))
        if tag in ("p", "div", "li", "br", "h4"):
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        if tag in ("p", "div", "li", "h4"):
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def text_content(html):
    parser = TextParser()
    parser.feed(html)
    text = " ".join("".join(parser.parts).split())
    text = re.sub(r"(?<=\d)(?=[¼½¾])", "-", text)
    return text.replace("¼", "1/4").replace("½", "1/2").replace("¾", "3/4").translate(
        str.maketrans({"\u2011": "-", "\u2010": "-", "\u2212": "-"})), parser.links


def official_link(value):
    url = urljoin(CALENDAR_URL, value)
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.netloc != "www.federalreserve.gov" or parts.query or parts.fragment:
        raise ValueError("Non-authoritative Fed URL")
    if not re.fullmatch(r"/newsevents/pressreleases/monetary\d{8}a(?:1)?\.htm", parts.path):
        raise ValueError("Unsupported Fed document")
    return url


def parse_calendar(html):
    """Read dated meeting rows, excluding notation votes and historical footnotes."""
    headings = list(re.finditer(r"(\d{4}) FOMC Meetings", html))
    rows = []
    for index, heading in enumerate(headings):
        section = html[heading.end():headings[index + 1].start() if index + 1 < len(headings) else len(html)]
        for block in re.split(r'<div\b[^>]*class="[^"]*\brow fomc-meeting\b[^\"]*"[^>]*>', section)[1:]:
            def field(name):
                match = re.search(r'<div\b[^>]*class="[^"]*\bfomc-meeting__' + name + r'\b[^\"]*"[^>]*>(.*?)</div>', block, re.S)
                return text_content(match[1])[0] if match else ""
            month, days = field("month"), field("date")
            if "notation" in days.lower():
                continue
            if not re.fullmatch(r"\d{1,2}(?:-\d{1,2})?\*?", days):
                raise ValueError("Unrecognized FOMC meeting date")
            # Cross-month meetings use the second month and final day.
            month_key = month.split("/")[-1].lower()
            matches = [value for key, value in MONTHS.items() if key == month_key or key[:3] == month_key]
            if len(matches) != 1:
                raise ValueError("Unrecognized FOMC month")
            scheduled = date(int(heading[1]), matches[0], int(days.rstrip("*").split("-")[-1]))
            _, links = text_content(block)
            suffix = scheduled.strftime("%Y%m%d")
            statement, note = None, None
            for link in links:
                if re.search(r"/monetary" + suffix + r"a(?:1)?\.htm$", link):
                    url = official_link(link)
                    if url.endswith("a1.htm"):
                        note = url
                    else:
                        statement = url
            rows.append({"date": scheduled, "statement": statement, "note": note})
    if not rows or len(rows) > 120 or len({r["date"] for r in rows}) != len(rows):
        raise ValueError("Invalid calendar snapshot")
    return sorted(rows, key=lambda row: row["date"])


def number(value):
    parts = value.replace("-", " ").split()
    return float(sum(Fraction(part) for part in parts))


def target_range(text):
    pattern = r"target range (?:for the federal funds rate |of )?(?:by " + NUMBER + r" percentage points? )?(?:at |to )?(" + NUMBER + r")\s+to\s+(" + NUMBER + r")\s+percent"
    matches = re.findall(pattern, text, re.I)
    values = {(number(low), number(high)) for low, high in matches}
    if len(values) != 1:
        raise ValueError("Missing or conflicting target range")
    low, high = next(iter(values))
    if not 0 <= low <= high <= 30 or high - low > 1:
        raise ValueError("Invalid target range")
    return EventValue(lower=low, upper=high, unit="percent")


def statement_document(html, url, retrieved_at):
    url = official_link(url)
    day = datetime.strptime(re.search(r"monetary(\d{8})a\.htm$", url)[1], "%Y%m%d").date()
    text, _ = text_content(html)
    if not re.search(day.strftime("%B") + rf"\s+0?{day.day},\s+{day.year}", text):
        raise ValueError("Missing publication date")
    release = re.search(r"For release at (\d{1,2}):(\d{2})\s+([ap])\.m\.\s+(EDT|EST)", text)
    if not release:
        raise ValueError("Unsupported announcement timing")
    hour = int(release[1]) % 12 + (12 if release[3] == "p" else 0)
    announced = datetime(day.year, day.month, day.day, hour, int(release[2]), tzinfo=ET)
    if announced.tzname() != release[4]:
        raise ValueError("Inconsistent announcement timezone")
    return SourceDocument(id=f"fed:statement:{day}", ticker="GLOBAL", title="FOMC Rate Decision",
        extracted_text=text[:60000], published_at=announced, observed_at=retrieved_at,
        source_name="Federal Reserve", source_type="government_source", source_url=url,
        provider="fomc", provider_document_id=str(day), source_quality="primary_authoritative")


def parse_decision(document, *, note_html=None, note_url=None, note_retrieved_at=None):
    if document.provider != "fomc" or document.source_quality != "primary_authoritative":
        raise ValueError("Unsupported statement provenance")
    official_link(str(document.source_url))
    text = document.extracted_text
    clauses = re.findall(r"The Committee decided to (?:raise|lower|maintain) the target range for the federal funds rate .*?percent\b", text, re.I)
    if len(clauses) != 1:
        raise ValueError("No unambiguous Committee decision")
    clause = clauses[0].lower()
    actual = target_range(clause)
    if "decided to maintain" in clause:
        delta = 0.0
    else:
        move = re.search(r"by (" + NUMBER + r") percentage point", clause)
        if not move:
            raise ValueError("Missing explicit rate change")
        delta = number(move[1]) * (1 if "decided to raise" in clause else -1)
    previous = EventValue(lower=actual.lower - delta, upper=actual.upper - delta, unit="percent")
    if previous.lower < 0:
        raise ValueError("Invalid previous target")
    provenance = [EventSource(source="Federal Reserve — FOMC Statement", source_type="government_source",
        source_url=document.source_url, published_at=document.published_at, retrieved_at=document.observed_at)]
    effective = None
    if note_html is not None:
        note_url = official_link(note_url)
        if not note_url.endswith(document.provider_document_id.replace("-", "") + "a1.htm"):
            raise ValueError("Implementation note belongs to another decision")
        note, _ = text_content(note_html)
        dates = re.findall(r"Effective (\w+ \d{1,2}, \d{4}), the Federal Open Market Committee directs the Desk", note)
        if len(dates) != 1 or target_range(note) != actual:
            raise ValueError("Conflicting implementation note")
        effective = datetime.strptime(dates[0], "%B %d, %Y").date()
        if effective < document.published_at.astimezone(ET).date():
            raise ValueError("Effective date precedes announcement")
        provenance.append(EventSource(source="Federal Reserve — Implementation Note", source_type="government_source",
            source_url=note_url, retrieved_at=note_retrieved_at or document.observed_at))
    day = document.published_at.astimezone(ET).date()
    return ExternalEvent(event_id=f"fomc:{day}", event_type="fomc_rate_decision", category="economic",
        title="FOMC Rate Decision", summary="The Federal Reserve announced its target federal funds range decision.",
        scheduled_date=day, announced_at=document.published_at, effective_date=effective,
        expires_at=document.published_at + timedelta(days=RECENT_DAYS), status="occurred",
        previous_value=previous, actual_value=actual, change=EventValue(amount=round(delta * 100, 8), unit="basis_points"),
        provenance=tuple(provenance), scope=EventScope(countries=("United States",), entities=("Federal Reserve",)))


class FomcSource:
    def __init__(self, settings, client=None, clock=lambda: datetime.now(timezone.utc)):
        self.settings, self.clock = settings, clock
        self.client = client or JsonClient(settings)
        self.cache = Cache(settings.outlook_failure_cache_ttl, capacity=1)
        self.requests = self.loads = self.reads = 0

    def _text(self, url):
        self.requests += 1
        return self.client.get_text(url, provider="fomc")

    def get_events(self):
        self.reads += 1
        return self.cache.get("shared", self._load, self.settings.outlook_fomc_cache_ttl)

    def _load(self):
        self.loads += 1
        calendar_html = self._text(CALENDAR_URL)
        now = self.clock()
        rows = parse_calendar(calendar_html)
        today = now.astimezone(ET).date()
        if not any(row["date"].year == today.year for row in rows):
            raise ProviderUnavailable("stale_calendar")
        upcoming = [row for row in rows if row["date"] >= today and not row["statement"]][:MAX_UPCOMING]
        recent = [row for row in rows if today - timedelta(days=RECENT_DAYS) <= row["date"] <= today and row["statement"]][-MAX_RECENT:]
        events, excluded = [], []
        for row in upcoming:
            events.append(ExternalEvent(event_id=f"fomc:{row['date']}", event_type="fomc_rate_decision", category="economic",
                title="FOMC Rate Decision", summary="Scheduled FOMC meeting decision date; meeting dates may be revised.",
                scheduled_date=row["date"], status="upcoming", scope=EventScope(countries=("United States",), entities=("Federal Reserve",)),
                provenance=(EventSource(source="Federal Reserve — FOMC Calendar", source_type="government_source",
                    source_url=CALENDAR_URL, retrieved_at=now),)))
        for row in recent:
            try:
                doc = statement_document(self._text(row["statement"]), row["statement"], self.clock())
                event = parse_decision(doc)
                if row["note"]:
                    try:
                        note_html = self._text(row["note"])
                        event = parse_decision(doc, note_html=note_html, note_url=row["note"], note_retrieved_at=self.clock())
                    except Exception:
                        excluded.append({"event_id": event.event_id, "reason": "implementation_unavailable_or_invalid"})
                events.append(event)
            except Exception:
                excluded.append({"event_id": f"fomc:{row['date']}", "reason": "statement_unavailable_or_invalid"})
        return {"events": events, "excluded": excluded, "retrieved_at": now.isoformat()}

