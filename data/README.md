# Product data

One YAML file per product: [`products/<id>.yaml`](products/). The id is the file name: lower-case letters, digits
and single dashes. The site, the downloads and the README tables are built from these files.

Downloads built from the same files: [products.csv](https://cyberanchor.github.io/antidetectDB/site/public/products.csv)
(one row per product) and [products.json](https://cyberanchor.github.io/antidetectDB/site/public/products.json) (the
records as they are here, with the id).

[`upstream.yaml`](upstream.yaml) holds the current stable Chrome and Firefox versions, the yardstick for the core lag.
`tools/upstream.py` writes it.

## Fields

Only `name`, `kind` and `status` are required. Empty and unknown values are left out: a missing field means nobody
has checked it yet, not "no".

| Field | Example | Meaning |
|---|---|---|
| `name` | `Octo Browser` | Product name as the vendor writes it |
| `kind` | `[browser, cloud-phone]` | `browser`: antidetect browser or profile manager · `cloud-phone`: Android phones in the cloud |
| `status` | `auto` | `checked`: installed and tested by hand (see `tests`) · `auto`: collected from the vendor's pages and the automatic checks, not tested · `pending`: little more than a name and a link |
| `dead` | `true` | The product is gone: the domain no longer resolves, the vendor closed it, or the project is archived. Left out otherwise |
| `successor` | `multilogin` | Id of the product that replaced a dead one |
| `website` | `https://octobrowser.net/` | Main site |
| `domains` | `[octobrowser.org]` | Other official domains |
| `legal_entity` | `BLACKBIRD SECURE BROWSING LTD` | The company that runs the product, as it names itself in its terms, privacy policy or site footer. Left out when the vendor does not say |
| `flag`, `country` | `🇬🇧`, `United Kingdom` | Country of the legal entity: where it is registered or has its stated address. Left out when the pages do not say |
| `alliance` | `5`, `9`, `14` | Five / Nine / Fourteen Eyes membership of that country |
| `law` | `Singapore` | The law that governs the terms of use, as the terms name it |
| `engine` | `[chromium, firefox]` | Browser engines: `chromium`, `firefox`, `webkit` |
| `cores` | `{name: Mimic, engine: chromium, version: '156'}` | The newest core of each engine the vendor ships, with the version the vendor states |
| `platforms` | `[windows, macos, linux]` | Where the app runs: `windows`, `macos`, `linux`, `android`, `ios`, `web` |
| `android` | `['12', '15']` | Cloud phones: Android versions on offer |
| `open_source` | `true` | `true`: the browser's source (engine changes included) is published under an open-source licence · `false`: closed, or only a wrapper or launcher is open, or the licence forbids commercial use |
| `repo` | `https://github.com/daijro/camoufox` | Source repository |
| `license` | `MPL-2.0` | Licence of the repository (SPDX id) |
| `stars`, `pushed` | `13192`, `'2026-11-11'` | GitHub stars and the date of the last push (automatic). Stars can be bought; read them as a hint |
| `release` | `{version: v2.27.3, date: '2026-11-09'}` | Latest release |
| `free` | `3 profiles` | What the free plan includes; `no` when there is none |
| `trial` | `7 days` | Time-limited trial |
| `price` | `[Starter $10/month (20 profiles)]` | Paid plans, cheapest first, as the pricing page shows them with monthly billing |
| `payment` | `[card, crypto]` | Payment methods |
| `storage` | `cloud` | Where profiles are kept: `cloud` (the vendor's servers), `local`, `both` |
| `api` | `true` | An automation API (local API, CDP, Selenium / Puppeteer / Playwright) on some plan |
| `tests` | see below | Results of the test by hand; required for `status: checked` |
| `incidents` | `{date: 2025-01, text: …, links: […]}` | Security incidents and data leaks, each with its sources |
| `note` | | What else is worth knowing, with dates |
| `links` | `{terms: …, privacy: …, pricing: …}` | `terms`, `privacy`, `imprint`, `pricing`, `download`, `changelog`, `docs` |
| `social` | `[https://t.me/…]` | Official accounts |
| `created`, `expires` | `'2019-04-02'` | Registration and expiry date of the website's domain (RDAP, automatic) |
| `online_since` | `'2019-05-11'` | First capture of the domain in the Wayback Machine (automatic) |
| `hosting` | `{ip: …, flag: 🇺🇸, country: United States, asn: AS13335 Cloudflare, Inc., org: …}` | Where the website is hosted (automatic) |
| `http` | `200` | Status code of the website at the last check; `0` no answer. A bot check (403) still counts as an answer |
| `sources` | | Pages the facts come from |
| `last_checked` | `'2026-11-11'` | Date of the last automatic check |

Dates, versions and anything else that starts with a digit are quoted so that YAML keeps them as text.

### Core lag

The site and the README show how many major versions each core is behind the current stable release:
Chrome for `chromium` cores (the release that serves most users, from Google's VersionHistory API) and Firefox for
`firefox` cores. A Firefox core on the current ESR is shown as `ESR`. An outdated core is a security risk (fixed
browser bugs stay open) and a detection signal (few real users run an old Chrome).

### `tests`

What was seen when a fresh profile of the product was tested by hand (status `checked`). Every value is short text,
as the test page shows it.

| Field | Meaning |
|---|---|
| `date`, `version` | Day of the test and the app version |
| `creepjs` | [CreepJS](https://abrahamjuliot.github.io/creepjs/): trust score and the number of lies |
| `pixelscan` | [Pixelscan](https://pixelscan.net/): the verdict |
| `browserscan` | [BrowserScan](https://www.browserscan.net/): authenticity score |
| `iphey` | [Iphey](https://iphey.com/): the verdict |
| `fingerprint_com` | [Fingerprint.com playground](https://demo.fingerprint.com/playground): bot / tampering detection |
| `webrtc` | [BrowserLeaks WebRTC](https://browserleaks.com/webrtc): whether the real IP leaks |
| `note` | Proxy used, anything unusual |

## Adding or changing a product

Edit or add the file in the format of the others, with a source link for every fact, and open a pull request.
Then run `python3 tools/test_data.py --no-site`. Facts without a source, marketing text and referral links are not
accepted. The site build stops with a message when a file is broken (an unknown field, a wrong type).
