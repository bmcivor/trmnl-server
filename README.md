# trmnl-server

Self-hosted server that renders Claude Code usage limits to a TRMNL 7.5" (OG)
e-ink panel. The device polls this server instead of TRMNL's cloud, so it
needs no registration and no account.

> **Not affiliated with, endorsed by, or supported by TRMNL.** This is an
> independent hobby project that implements TRMNL's publicly documented BYOS
> API so a self-built device can display something useful. TRMNL is a
> trademark of its owner.

## How it works

1. A Claude Code **statusline hook** receives the `rate_limits` object that
   Claude Code pipes to the statusline command on every render, and writes it
   to a state file.
2. This **server** reads that state file, computes reset countdowns, renders
   an 800x480 1-bit BMP, and serves it over the TRMNL device API.
3. The **device** wakes, calls `/api/display`, downloads the image, draws it,
   and sleeps until the next refresh.

All drawing happens server-side. The device never renders anything itself; it
downloads a finished bitmap and pushes it to the panel.

## API endpoints

Implemented against the contract used by Terminus, TRMNL's reference BYOS.

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/api/setup` | GET | Issues `api_key` and `friendly_id` to a new device |
| `/api/display` | GET | Renders the screen and returns its URL plus refresh rate |
| `/api/log` | POST | Accepts device log batches, returns 204 |
| `/screen.bmp` | GET | Renders and serves the current image |

## Security

**There is no authentication.** Any device that calls `/api/setup` is issued
the configured credentials, and `/api/display` does not check the
`Access-Token` header the firmware sends. Anything that can reach the port
can fetch your usage screen.

That is fine on a trusted LAN, which is what this was built for. Do not
expose it to the internet as-is.

## Install

```
uv sync
```

## Run

```
uv run trmnl-server
```

On start it logs the base URL the device should use. Override anything with
environment variables:

| Variable | Default | Meaning |
| --- | --- | --- |
| `TRMNL_HOST` | `0.0.0.0` | Bind interface |
| `TRMNL_PORT` | `2300` | Bind port |
| `TRMNL_BASE_URL` | autodetected LAN address | URL the device fetches images from |
| `TRMNL_STATE_FILE` | `~/.claude/trmnl-usage.json` | Where the hook writes state |
| `TRMNL_REFRESH_RATE` | `900` | Seconds the device sleeps between polls |
| `TRMNL_API_KEY` | `local-byos-key` | Token issued at setup |
| `TRMNL_FRIENDLY_ID` | `CLAUDE` | Device identifier issued at setup |

If autodetection cannot find a routable address it falls back to `127.0.0.1`
and logs an error. The device cannot reach that, so set `TRMNL_BASE_URL`
explicitly if you see it.

## Statusline hook

Add to `~/.claude/settings.json`, using the path where you cloned this repo:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 /path/to/trmnl-server/scripts/statusline_hook.py"
  }
}
```

The hook uses only the standard library, so it does not need this project's
virtual environment. It prints a short summary to the status bar and writes
the state file as a side effect.

`rate_limits` is only present for Claude.ai subscribers on Claude Code 2.1.80
or newer, and only appears after the first API response in a session. Usage
percentages therefore only change while you are actively using Claude Code;
reset countdowns are computed locally from `resets_at`, so an expired window
zeroes itself without needing a fresh reading.

## Pointing the device at this server

In the device's captive portal, set the **API server** field to the base URL
logged at start-up, for example `http://192.168.1.50:2300`. Use plain HTTP.

To get a configured device back into the portal, click RESET, release, then
hold KEY3 for five seconds.

## Known issue: WSL networking

If this server runs inside WSL2, its default NAT mode means the device cannot
reach it from the LAN even though the port is open inside WSL. Three ways
around it, none applied by this project:

- Windows `netsh interface portproxy` forwarding to the WSL address
- WSL mirrored networking (`networkingMode=mirrored` in `.wslconfig`)
- Running the server on the Windows side, reading the state file over the
  `\\wsl.localhost\...` share

Pick one deliberately; each changes host networking. Note that a portproxy
rule breaks whenever WSL's IP changes on reboot.

## Battery note

Battery life scales roughly linearly with poll frequency. Seeed quote about
three months from the 2000 mAh cell at a six-hour refresh, which works out
near two weeks at hourly polling and a few days at fifteen minutes. Set
`TRMNL_REFRESH_RATE` accordingly, or run the device on USB power.

## Development

```
uv run pytest
```

```
uv run ruff check .
```

```
uv run mypy
```

## Licence

MIT. See [LICENSE](LICENSE).
