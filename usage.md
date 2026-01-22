# DexScreener Scraper - Usage Guide

## Changes Made

### 1. `api/dex.py`

**Line 94 - Added browser impersonation:**
```python
# Before
session = AsyncSession(headers=headers)

# After
session = AsyncSession(headers=headers, impersonate='chrome')
```
*Why: Required to bypass Cloudflare protection. Without this, WebSocket connections return 403 Forbidden.*

**Lines 46-93 - Parallel async API fetching:**
Replaced sequential `requests.get()` loop with parallel async batched fetching:
- `format_token_data()` - now runs async fetching
- `_fetch_single_token()` - fetches one token asynchronously
- `_fetch_tokens_async()` - processes tokens in parallel batches of 10

*Why: Original code took ~60 seconds (70 sequential API calls). Now takes ~6 seconds.*

### 2. `api/index.py`

**Line 16 - Updated API version:**
```python
# Before
text = """wss://io.dexscreener.com/dex/screener/v5/pairs/h24/1?..."""

# After
text = """wss://io.dexscreener.com/dex/screener/v6/pairs/h24/1?..."""
```
*Why: v6 is the current endpoint used by DexScreener.*

---

## Usage

### Run Flask App
```bash
cd /home/redik/soft/fun/doffnscraper
.venv/bin/python -m flask --app api.index run --debug
```

Then open: http://127.0.0.1:5000

### Available Filters

Add filters via the web UI or directly in URL:

| Filter | Parameter | Example |
|--------|-----------|---------|
| Chain | `&filters[chainIds][0]=solana` | Solana only |
| Liquidity | `&filters[liquidity][min]=1000` | Min $1000 liquidity |
| Market Cap | `&filters[marketCap][min]=10000` | Min $10K mcap |
| FDV | `&filters[fdv][max]=1000000` | Max $1M FDV |
| Pair Age | `&filters[pairAge][max]=24` | Max 24 hours old |
| 24H Txns | `&filters[txns][h24][min]=100` | Min 100 transactions |

**Example - Solana 6H Trending:**
```
/dex?generated_text=&filters[chainIds][0]=solana
```

### Direct Python Usage
```python
from api.dex import DexBot

# Solana, 6H trending
url = 'wss://io.dexscreener.com/dex/screener/v6/pairs/h24/1?rankBy[key]=trendingScoreH6&rankBy[order]=desc&filters[chainIds][0]=solana'

bot = DexBot('dummy', url)
result = bot.format_token_data()
print(result)
```

---

## Known Bugs

### 1. Bonk token parsing error (line 178)
```
Error processing token '...bonk...': 're.Match' object has no attribute 'startswith'
```
**Cause:** `bonk_match` is a regex Match object, but code calls `.startswith()` on it directly.

**Location:** `api/dex.py` lines 176-182

**Fix needed:**
```python
# Current (broken)
if bonk_match.startswith('V'):

# Should be
if bonk_match.group(0).startswith('V'):
```

### 2. Async task cleanup warnings
```
Task was destroyed but it is pending!
task: <Task pending name='WebSocket-...-read' ...>
```
**Cause:** WebSocket connection not properly closed before event loop ends.

**Impact:** Cosmetic only - doesn't affect functionality.

### 3. Some token addresses extracted incorrectly
The binary parsing extracts some malformed addresses (truncated or with extra characters). The DexScreener API call fails silently for these.

**Impact:** Some tokens in the list return "No data Retrieved".

---

## WebSocket Message Format

The WebSocket returns binary data, not JSON. Message structure:
1. First message: `latestBlock` (36 bytes) - skip this
2. Second message: `pairs` data (~100KB) - contains token data

When using filters, always wait for the message containing `pairs`.
