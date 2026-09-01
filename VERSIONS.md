# Versions

| Component | Version | Checked |
|---|---|---|
| `mcp` (Python SDK) | 2.x, with a 1.x fallback | 2026-09-01 |
| `osxphotos` | 0.76.1 | 2026-09-01 |
| `photoscript` | 0.3.x | 2026-09-01 |
| Photos library schema | DB 5001, model 19607, Photos 11.1 | 2026-09-01 |
| Python | 3.11, 3.12, 3.13 | 2026-09-01 |

## 0.1.0, 2026-09-01

First release.

Searches Apple's own on-device machine learning index rather than filenames and
typed metadata: scene labels, text read out of images, activities, venue types
and reverse geocoded places. Verified against a 37,129 item library where only
3 items had a title and 3 had keywords, but 35,983 carried scene labels and
10,852 carried readable text.

Ranking is tuned against the failure that matters. A screenshot full of OCR text
otherwise matches almost any query, so matches resting only on text found inside
an image are scored down, and screenshots compete at a discount unless the query
is asking for one.

Words Apple has no concept of come back in `unmatched_terms` with suggestions
from the vocabulary that does exist, instead of silently returning noise.

`look_at_photos` renders from Apple's cached derivatives rather than the
original, so previews work for assets that live only in iCloud. In the test
library 36,996 of 37,129 assets had no local original and every preview still
rendered.

Writes work by default. `archive_photos` requires `confirm: true`.
`APPLE_PHOTOS_READ_ONLY=1` removes the write tools from the list entirely.
