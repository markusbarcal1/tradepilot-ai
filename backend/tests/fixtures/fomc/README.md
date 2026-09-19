# Frozen Federal Reserve source fixtures

Retrieved September 19, 2026 UTC with the application's ordinary HTTP headers.
These are real-source HTML extracts, not synthetic FOMC rate outcomes.

- `calendar.html`: only the 2026 meeting panel from https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
- `september-statement.html`: main-content onward from https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm
- `september-implementation.html`: main-content onward from https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a1.htm
- `july-statement.html`: main-content onward from https://www.federalreserve.gov/newsevents/pressreleases/monetary20260729a.htm
- `july-implementation.html`: main-content onward from https://www.federalreserve.gov/newsevents/pressreleases/monetary20260729a1.htm

No HTML fixture exceeds 20 KiB. The production HTTP response bound is 1 MiB.
Source: Federal Reserve Board; see https://www.federalreserve.gov/disclaimer.htm
for its public-domain information and attribution policy.

Tests explicitly construct synthetic probability distributions, altered statements,
company classifications, failure cases, and replay clocks. Those controls are not
claimed as actual historical market expectations or a production source.
