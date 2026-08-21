# trmnl-server

Self-hosted TRMNL BYOS server that renders Claude Code usage limits to a
TRMNL 7.5" (OG) e-ink panel.

The device polls this server instead of TRMNL's cloud, so it needs no
registration, no friendly ID from TRMNL, and no account.

## How it works

1. A Claude Code **statusline hook** receives the `rate_limits` object that
   Claude Code pipes to the statusline command on every render, and writes it
   to a state file.
2. This **server** reads that state file, computes reset countdowns, renders
   an 800x480 1-bit BMP, and serves it over the TRMNL device API.
3. The **device** wakes, calls `/api/display`, downloads the image, draws it,
   and sleeps until the next refresh.

## API endpoints

Implemented against the contract used by Terminus, TRMNL's reference BYOS.

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/api/setup` | GET | Issues `api_key` and `friendly_id` to a new device |
| `/api/display` | GET | Renders the screen and returns its URL plus refresh rate |
| `/api/log` | POST | Accepts device log batches, returns 204 |
| `/screen.bmp` | GET | Serves the rendered image |
| `/preview` | GET | Renders on demand for checking in a browser |

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

## Statusline hook

Add to `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 /home/blake_mcivor/Development/trmnl-server/scripts/statusline_hook.py"
  }
}
```

The hook uses only the standard library, so it does not need this project's
virtual environment. It prints a short summary to the status bar and writes
the state file as a side effect.

`rate_limits` is only present for Claude.ai subscribers on Claude Code 2.1.80
or newer, and only appears after the first API response in a session.

## Pointing the device at this server

In the device's captive portal, set the **API server** field to the base URL
logged at start-up, for example `http://192.168.1.50:2300`. Use plain HTTP.

## Known issue: WSL networking

If this server runs inside WSL2, its default NAT mode means the ESP32 cannot
reach it from the LAN even though the port is open inside WSL. Three ways
around it, none applied by this project:

- Windows `netsh interface portproxy` forwarding to the WSL address
- WSL mirrored networking (`networkingMode=mirrored` in `.wslconfig`)
- Running the server on the Windows side, reading the state file over
  `\\wsl.localhost\...`

Pick one deliberately; each changes host networking.

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
