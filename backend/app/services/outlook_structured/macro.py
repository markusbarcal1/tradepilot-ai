"""Bounded BLS/BEA announcement adapters; no series polling or inferred consensus."""
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import re
from threading import RLock
from urllib.parse import urljoin, urlsplit

from app.models.outlook_event import (ExternalEvent, EventMeasurement, EventRevision,
    EventScope, EventSource, EventValue)
from .fomc import ET, MONTHS, text_content
from .transport import Cache, JsonClient

BLS_CALENDAR = "https://www.bls.gov/schedule/news_release/bls.ics"
BEA_CALENDAR = "https://www.bea.gov/news/schedule/ics/online-calendar-subscription.ics"
BEA_CURRENT = "https://www.bea.gov/news/current-releases"
BLS_RELEASES = {"cpi": "https://www.bls.gov/news.release/cpi.nr0.htm",
                "employment": "https://www.bls.gov/news.release/empsit.nr0.htm"}
TITLES = {"cpi": "CPI Inflation", "pce": "PCE Inflation",
          "employment": "Employment Situation", "gdp": "GDP"}
UPCOMING_DAYS = 45
RECENT_DAYS = 60
NUMBER = r"[+-]?\d[\d,]*(?:\.\d+)?"
MONTH = "(?:" + "|".join(MONTHS) + ")"


def family(title):
    if title == "Consumer Price Index":
        return "cpi"
    if title == "Employment Situation":
        return "employment"
    if title.startswith("Personal Income and Outlays,"):
        return "pce"
    if re.match(r"(?:GDP|Gross Domestic Product)(?:,| \()", title):
        return "gdp"
    return None


def reference(title, kind):
    if kind == "gdp":
        match = re.search(r"([1-4])(?:st|nd|rd|th) Quarter(?: and Year)? (\d{4})", title, re.I)
        period = f"{match[2]}-Q{match[1]}" if match else None
        estimate = re.search(r"\b(Advance|Second|Third) Estimate\b", title, re.I)
        return period, estimate[0].title() if estimate else None
    match = re.search(r"\b(" + MONTH + r") (\d{4})\b", title, re.I)
    # A combined-month release needs a dedicated parser; never silently pick its last month.
    if re.search(MONTH + r" and " + MONTH, title, re.I):
        return None, None
    return (f"{match[2]}-{MONTHS[match[1].lower()]:02d}" if match else None), None


def source(url, now, announced=None):
    host = urlsplit(url).netloc
    if host not in ("www.bls.gov", "www.bea.gov") or urlsplit(url).scheme != "https":
        raise ValueError("Unsupported macro authority")
    return EventSource(source="Bureau of Labor Statistics" if host == "www.bls.gov" else "Bureau of Economic Analysis",
        source_type="government_source", source_url=url, retrieved_at=now, published_at=announced)


def make_event(kind, at, provenance, *, period=None, estimate=None, released=False, measurements=(), revisions=()):
    if not measurements and not released:
        keys = {"cpi": (("headline_mom", "Headline CPI MoM"), ("core_mom", "Core CPI MoM"),
                         ("headline_yoy", "Headline CPI YoY"), ("core_yoy", "Core CPI YoY")),
                "pce": (("headline_mom", "Headline PCE MoM"), ("core_mom", "Core PCE MoM"),
                         ("headline_yoy", "Headline PCE YoY"), ("core_yoy", "Core PCE YoY")),
                "employment": (("payrolls", "Nonfarm payroll change"), ("unemployment", "Unemployment rate")),
                "gdp": (("real_gdp", "Real GDP growth (quarterly, annualized)"),)}
        measurements = [EventMeasurement(key=key, label=label) for key, label in keys[kind]]
    return ExternalEvent(event_id=f"{kind}:{at.astimezone(ET).date()}", event_type=f"macro_{kind}", category="economic",
        title=TITLES[kind], summary=f"{'Published' if released else 'Scheduled'} U.S. {TITLES[kind]} release.",
        scheduled_date=at.astimezone(ET).date(), scheduled_at=at, scheduled_timezone="America/New_York",
        announced_at=at if released else None, expires_at=at + timedelta(days=RECENT_DAYS) if released else None,
        reference_period=period, underlying_event_id=f"{kind}:{period}" if period else None,
        release_type=estimate or ("Initial release" if kind != "gdp" else None),
        status="occurred" if released else "upcoming", measurements=tuple(measurements), revisions=tuple(revisions),
        provenance=(provenance,), scope=EventScope(countries=("United States",)))


def parse_calendar(payload, url, now):
    """Strict subset of the official ICS formats; UTC or explicit Eastern only."""
    if "BEGIN:VCALENDAR" not in payload or "END:VCALENDAR" not in payload:
        raise ValueError("Not an iCalendar")
    lines = []
    for line in payload.replace("\r", "").split("\n"):
        if not line:
            continue
        if line.startswith((" ", "\t")) and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    events = {}
    for block in "\n".join(lines).split("BEGIN:VEVENT\n")[1:]:
        block = block.split("END:VEVENT", 1)[0]
        title = re.search(r"^SUMMARY:(.*)$", block, re.M)
        if not title:
            continue
        title = title[1].replace(r"\,", ",").replace(r"\;", ";")
        kind = family(title)
        if not kind or (url == BLS_CALENDAR) != (kind in BLS_RELEASES):
            continue
        if re.search(r"^STATUS:CANCELLED$", block, re.M):
            continue
        stamp = re.search(r"^DTSTART([^:]*):(\d{8}T\d{6}Z?)$", block, re.M)
        if not stamp:
            raise ValueError("Unsupported scheduled time")
        if stamp[2].endswith("Z"):
            at = datetime.strptime(stamp[2], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone(ET)
        elif stamp[1] in (";TZID=US-Eastern", ";TZID=America/New_York"):
            at = datetime.strptime(stamp[2], "%Y%m%dT%H%M%S").replace(tzinfo=ET)
        else:
            raise ValueError("Unspecified calendar timezone")
        period, estimate = reference(title, kind)
        event = make_event(kind, at, source(url, now), period=period, estimate=estimate)
        if event.event_id in events and events[event.event_id] != event:
            raise ValueError("Conflicting scheduled releases")
        events[event.event_id] = event
    if not events:
        raise ValueError("No supported calendar events")
    return sorted(events.values(), key=lambda e: (e.scheduled_at, e.event_id))


class Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def table_values(html, label):
    parser = Tables()
    parser.feed(html)
    matches = [r[1:] for r in parser.rows if r and r[0].casefold() == label.casefold()]
    if len(matches) != 1 or not all(re.fullmatch(NUMBER, x) for x in matches[0]):
        raise ValueError("Missing or ambiguous measurement row")
    return [float(x.replace(",", "")) for x in matches[0]]


def measurement(key, label, amount, unit="percent", previous=None):
    return EventMeasurement(key=key, label=label, actual_value=EventValue(amount=amount, unit=unit),
        previous_value=EventValue(amount=previous, unit=unit) if previous is not None else None)


def signed(verb, amount):
    value = float(amount.replace(",", ""))
    return -value if verb.lower() in ("decreased", "declined", "fell") else value


def publication(text, now):
    # Only the embargo header, never a footer's next-release date.
    header = re.search(r"embargoed until(.{0,180})", text, re.I)
    match = re.search(r"(\d{1,2}):(\d{2}) ([ap])\.m\. (?:\((ET)\)|(EDT|EST)),? \w+, (\w+ \d{1,2}, \d{4})", header[1] if header else "")
    if not match:
        raise ValueError("Missing publication timestamp")
    day = datetime.strptime(match[6], "%B %d, %Y")
    at = day.replace(hour=int(match[1]) % 12 + (12 if match[3] == "p" else 0), minute=int(match[2]), tzinfo=ET)
    if at > now or (match[5] and match[5] != at.tzname()):
        raise ValueError("Future or inconsistent publication")
    return at


def parse_release(html, kind, url, now):
    if kind in BLS_RELEASES:
        if url != BLS_RELEASES[kind]:
            raise ValueError("Unsupported BLS release URL")
    elif not re.fullmatch(r"https://www\.bea\.gov/news/\d{4}/[a-z0-9-]+", url):
        raise ValueError("Unsupported BEA release URL")
    text = text_content(html)[0]
    at = publication(text, now)
    provenance = source(url, now, at)
    revisions = []
    if kind in BLS_RELEASES:
        title = re.search((r"CONSUMER PRICE INDEX" if kind == "cpi" else r"THE EMPLOYMENT SITUATION") + r"\s*-\s*(" + MONTH + r" \d{4})", text, re.I)
    else:
        headings = re.findall(r"<h1\b[^>]*>(.*?)</h1>", html, re.S | re.I)
        titles = [text_content(h)[0] for h in headings if family(text_content(h)[0]) == kind]
        title = [titles[0], titles[0]] if len(titles) == 1 else None
    if not title:
        raise ValueError("Unrecognized release title")
    period, estimate = reference(title[1], kind)
    if not period or (kind == "gdp" and not estimate):
        raise ValueError("Missing reference period or estimate")
    period_title = f"{period[5:]} {period[:4]}" if kind == "gdp" else datetime.strptime(period, "%Y-%m").strftime("%B %Y")
    provenance = provenance.model_copy(update={"source": f"{provenance.source} — {TITLES[kind]}, {period_title}"})
    if kind == "cpi":
        # Official summary Table A: latest SA monthly column followed by NSA 12-month change.
        if "Seasonally adjusted changes from preceding month" not in text or "12-mos." not in text:
            raise ValueError("Unsupported CPI table units")
        table = re.search(r'<table\b[^>]*id="cpi_pressa"[^>]*>(.*?)</table>', html, re.S)
        if not table:
            raise ValueError("Missing CPI summary table")
        headers = re.findall(r'<th\b[^>]*id="cpi_pressa.h.2.\d+"[^>]*>(.*?)</th>', table[1], re.S)
        latest = text_content(headers[-1])[0].replace(".", "") if headers else ""
        expected_month = datetime.strptime(period, "%Y-%m")
        if latest != expected_month.strftime("%b %Y"):
            raise ValueError("CPI reference period mismatch")
        values = []
        for label, key, name in (("All items", "headline", "Headline CPI"),
                                 ("All items less food and energy", "core", "Core CPI")):
            row = table_values(table[0], label)
            if len(row) != len(headers) + 1:
                raise ValueError("Incomplete CPI columns")
            values += [measurement(f"{key}_mom", f"{name} MoM (seasonally adjusted)", row[-2]),
                       measurement(f"{key}_yoy", f"{name} YoY (not seasonally adjusted)", row[-1])]
    elif kind == "pce":
        values = []
        for label, key, name in (("PCE price index", "headline", "Headline PCE"),
                                 ("PCE price index excluding food and energy", "core", "Core PCE")):
            row = table_values(html, label)
            if len(row) != 2 or "Percent change from preceding month" not in text:
                raise ValueError("Unsupported PCE table")
            values.append(measurement(f"{key}_mom", f"{name} MoM (seasonally adjusted)", row[-1]))
        yoy = re.search(r"From the same month one year ago, the PCE price index(?: for \w+)? (increased|decreased) (" + NUMBER + r") percent\. Excluding food and energy, the PCE price index (?:also )?(increased|decreased) (" + NUMBER + r") percent", text)
        if not yoy:
            raise ValueError("Unsupported PCE annual changes")
        values += [measurement("headline_yoy", "Headline PCE YoY", signed(yoy[1], yoy[2])),
                   measurement("core_yoy", "Core PCE YoY", signed(yoy[3], yoy[4]))]
    elif kind == "employment":
        lead = text.split(title[0], 1)[1].split("Household Survey Data", 1)[0]
        payroll = re.search(r"Total nonfarm payroll employment (increased|decreased|rose|fell)(?: by)? (" + NUMBER + r")", lead)
        # Accept only an explicit published total; 'little changed' alone is not zero.
        if not payroll:
            payroll = re.search(r"Total nonfarm payroll employment (?:was little changed|changed little).*?\(([+-]\d[\d,]*)\)", lead)
            count = float(payroll[1].replace(",", "")) if payroll else None
        else:
            count = signed(payroll[1], payroll[2])
        unemployment = re.search(r"the unemployment rate,? (?:was |remained |changed |edged |rose |fell |increased |decreased |declined |little |unchanged |up |down |at |to )*(" + NUMBER + r") percent", lead)
        if count is None or not unemployment:
            raise ValueError("Incomplete employment measurements")
        values = [measurement("payrolls", "Nonfarm payroll change (seasonally adjusted)", count, "jobs"),
                  measurement("unemployment", "Unemployment rate (seasonally adjusted)", float(unemployment[1]))]
        for rev in re.finditer(r"(?:change in total nonfarm payroll employment for|change for) (" + MONTH + r") was revised (?:up|down) by " + NUMBER + r", from (" + NUMBER + r") to (" + NUMBER + r")", text, re.I):
            month = MONTHS[rev[1].lower()]
            year = int(period[:4]) - (month > int(period[5:]))
            revisions.append(EventRevision(reference_period=f"{year}-{month:02d}", measurement_key="payrolls",
                previous_value=EventValue(amount=float(rev[2].replace(",", "")), unit="jobs"),
                actual_value=EventValue(amount=float(rev[3].replace(",", "")), unit="jobs"), provenance=provenance))
    else:
        growth = re.search(r"Real gross domestic product \(GDP\) (increased|decreased) at an annual rate of (" + NUMBER + r") percent", text)
        if not growth:
            raise ValueError("Unsupported GDP headline")
        actual = signed(growth[1], growth[2])
        previous = None
        if estimate != "Advance Estimate":
            row = table_values(html, "Real GDP")
            if len(row) != 2 or row[-1] != actual:
                raise ValueError("Conflicting GDP estimate table")
            previous = row[0]
            revisions.append(EventRevision(reference_period=period, measurement_key="real_gdp",
                previous_value=EventValue(amount=previous, unit="percent_saar"),
                actual_value=EventValue(amount=actual, unit="percent_saar"), provenance=provenance))
        values = [measurement("real_gdp", "Real GDP growth (quarterly, annualized)", actual, "percent_saar", previous)]
    return make_event(kind, at, provenance, period=period, estimate=estimate, released=True, measurements=values, revisions=revisions)


def next_bls_release(html, kind, now):
    text = text_content(html)[0]
    match = re.search(r"(?:Consumer Price Index news release|Employment Situation) for (" + MONTH +
        r" \d{4}) is scheduled to be published on \w+, (\w+ \d{1,2}, \d{4}),? at (\d{1,2}):(\d{2}) ([ap])\.m\. \(ET\)", text, re.I)
    if not match:
        return None
    at = datetime.strptime(match[2], "%B %d, %Y").replace(
        hour=int(match[3]) % 12 + (12 if match[5].lower() == "p" else 0), minute=int(match[4]), tzinfo=ET)
    period, _ = reference(match[1], kind)
    return make_event(kind, at, source(BLS_RELEASES[kind], now), period=period)


def release_links(html):
    links = {}
    for href, body in re.findall(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
        kind = family(text_content(body)[0])
        url = urljoin(BEA_CURRENT, href)
        if kind in ("pce", "gdp") and re.fullmatch(r"https://www\.bea\.gov/news/\d{4}/[a-z0-9-]+", url):
            if kind in links and links[kind] != url:
                raise ValueError("Ambiguous latest release")
            links[kind] = url
    return links


class MacroSource:
    """Shared endpoint caches; every family and calendar fails independently."""
    def __init__(self, settings, client=None, clock=lambda: datetime.now(timezone.utc), cache=None):
        self.settings, self.clock = settings, clock
        self.client = client or JsonClient(settings)
        self.cache = cache or Cache(settings.outlook_failure_cache_ttl, capacity=16)
        self.requests = self.loads = self.reads = 0
        self.published, self.lock = OrderedDict(), RLock()

    def _reconcile(self, event):
        """Bounded, process-local correction history; polling never creates a new release."""
        with self.lock:
            previous = self.published.get(event.event_id)
            if previous:
                if previous.reference_period != event.reference_period:
                    raise ValueError("Published reference period changed")
                old = {m.key: m.actual_value for m in previous.measurements}
                changes = [EventRevision(reference_period=event.reference_period, measurement_key=m.key,
                    previous_value=old[m.key], actual_value=m.actual_value,
                    provenance=event.provenance[0].model_copy(update={"published_at": None}),
                    previous_provenance=previous.provenance[0]) for m in event.measurements
                    if m.key in old and old[m.key] != m.actual_value]
                if changes:
                    event = event.model_copy(update={"revisions": (*previous.revisions, *changes)[-12:],
                        "release_type": "Updated release" if event.event_type != "macro_gdp" else event.release_type})
                elif previous.revisions:
                    event = event.model_copy(update={"revisions": previous.revisions, "release_type": previous.release_type})
            self.published[event.event_id] = event
            self.published.move_to_end(event.event_id)
            while len(self.published) > 32:
                self.published.popitem(last=False)
            return event

    def _get(self, url, parser, ttl):
        def load():
            self.requests += 1
            return parser(self.client.get_text(url, provider="macro"))
        return self.cache.get(url, load, ttl)

    def get_events(self):
        self.reads += 1
        before = self.requests
        now, events, excluded = self.clock(), {}, []
        calendars = []
        for url in (BLS_CALENDAR, BEA_CALENDAR):
            try:
                rows = self._get(url, lambda html: parse_calendar(html, url, self.clock()), 21600)
                if not any(e.scheduled_at > now for e in rows):
                    raise ValueError("Stale calendar")
                calendars.extend(rows)
            except Exception:
                excluded.append({"source": url, "reason": "calendar_unavailable_or_invalid"})
        for kind in TITLES:
            rows = [e for e in calendars if e.event_type == f"macro_{kind}" and now - timedelta(hours=24) <= e.scheduled_at <= now + timedelta(days=UPCOMING_DAYS)]
            for event in rows[:2]:
                events[event.event_id] = event
        # Never let a pre-release cache entry hide the release for a full ordinary TTL.
        upcoming = [e.scheduled_at for e in calendars if e.scheduled_at > now]
        due = any(now - timedelta(hours=24) <= e.scheduled_at <= now for e in calendars)
        ordinary_ttl = self.settings.outlook_macro_cache_ttl
        ttl = 300 if due else min(ordinary_ttl, max(1, (min(upcoming) - now).total_seconds())) if upcoming else ordinary_ttl
        urls = dict(BLS_RELEASES)
        try:
            urls.update(self._get(BEA_CURRENT, release_links, ttl))
        except Exception:
            excluded.append({"source": BEA_CURRENT, "reason": "release_index_unavailable_or_invalid"})
        for kind in TITLES:
            try:
                url = urls[kind]
                def parse(html):
                    event = parse_release(html, kind, url, self.clock())
                    following = next_bls_release(html, kind, self.clock()) if kind in BLS_RELEASES else None
                    return event, following
                event, following = self._get(url, parse, ttl if kind in BLS_RELEASES else 86400)
                if following and now <= following.scheduled_at <= now + timedelta(days=UPCOMING_DAYS):
                    existing = events.get(following.event_id)
                    # The live calendar controls timing; the release footer supplies only explicit period identity.
                    if existing:
                        events[following.event_id] = existing.model_copy(update={"reference_period": following.reference_period,
                            "underlying_event_id": following.underlying_event_id,
                            "provenance": (*existing.provenance, *following.provenance)})
                    elif not any(e.event_type == following.event_type for e in calendars):
                        events[following.event_id] = following
                scheduled = next((e for e in calendars if e.event_id == event.event_id), None)
                if scheduled:
                    if scheduled.reference_period and scheduled.reference_period != event.reference_period:
                        raise ValueError("Calendar reference period conflict")
                    event = event.model_copy(update={"scheduled_at": scheduled.scheduled_at,
                        "provenance": (*event.provenance, *scheduled.provenance)})
                events[event.event_id] = self._reconcile(event)
            except Exception:
                excluded.append({"family": kind, "reason": "release_unavailable_or_invalid"})
        if self.requests != before:
            self.loads += 1
        family_status = {}
        for kind in TITLES:
            rows = [e for e in events.values() if e.event_type == f"macro_{kind}"]
            released = any(e.announced_at and e.expires_at > now for e in rows)
            scheduled = any(not e.announced_at and e.scheduled_at >= now for e in rows)
            family_status[kind] = "available" if released and scheduled else "partial" if released or scheduled else "unavailable"
        agency_status = {}
        for agency, kinds in (("bls", ("cpi", "employment")), ("bea", ("pce", "gdp"))):
            statuses = {family_status[k] for k in kinds}
            agency_status[agency] = "available" if statuses == {"available"} else "unavailable" if statuses == {"unavailable"} else "partial"
        return {"events": list(events.values()), "excluded": excluded, "retrieved_at": now.isoformat(),
                "agency_status": agency_status, "family_status": family_status,
                "upcoming_horizon_days": UPCOMING_DAYS, "recent_horizon_days": RECENT_DAYS,
                "release_cache_ttl_seconds": ttl, "calendar_cache_ttl_seconds": 21600}
