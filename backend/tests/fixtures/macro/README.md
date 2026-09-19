# Frozen primary-source macro fixtures

Retrieved on September 19, 2026 using the application's bounded HTTP transport.
These are saved public government responses, never production fallback data.
Line endings/trailing whitespace are normalized and ICS continuation lines unfolded.
Tests are offline. Synthetic changes to these responses and synthetic consensus
snapshots appear only in `test_outlook_macro.py` and frontend tests.

| File | Official source |
| --- | --- |
| bls.ics | https://www.bls.gov/schedule/news_release/bls.ics |
| bea.ics | https://www.bea.gov/news/schedule/ics/online-calendar-subscription.ics |
| bea-current.html | https://www.bea.gov/news/current-releases |
| cpi.html | https://www.bls.gov/news.release/cpi.nr0.htm |
| employment.html | https://www.bls.gov/news.release/empsit.nr0.htm |
| pce.html | https://www.bea.gov/news/2026/personal-income-and-outlays-july-2026 |
| gdp.html | https://www.bea.gov/news/2026/gdp-second-estimate-and-corporate-profits-2nd-quarter-2026 |

The frontend macro JSON fixture combines these parsed releases with the existing
FOMC fixture and synthetic ABTC classification. It is an offline presentation
fixture, not a second production provider or expectation feed.
