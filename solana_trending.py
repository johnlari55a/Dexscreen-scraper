#!/usr/bin/env python3
"""
Solana Trending Tokens Scraper (6H timeframe)
Uses curl_cffi approach from doffn's repo to bypass Cloudflare
Equivalent to: dexscreener.com/solana/?rankBy=trendingScoreH6&order=desc
"""
import asyncio
from curl_cffi.requests import AsyncSession
import os
import base64
import re
import json
import requests

async def get_trending_tokens():
    """Connect to DexScreener WebSocket and get trending token addresses"""
    headers = {
        'Host': 'io.dexscreener.com',
        'Connection': 'Upgrade',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
        'Upgrade': 'websocket',
        'Origin': 'https://dexscreener.com',
        'Sec-WebSocket-Version': '13',
        'Sec-WebSocket-Key': base64.b64encode(os.urandom(16)).decode()
    }

    # Solana only, 6H trending score (v6 endpoint)
    url = 'wss://io.dexscreener.com/dex/screener/v6/pairs/h24/1?rankBy[key]=trendingScoreH6&rankBy[order]=desc&filters[chainIds][0]=solana'

    print("Connecting to DexScreener WebSocket (Solana, 6H trending)...")
    session = AsyncSession(headers=headers, impersonate='chrome')

    try:
        ws = await session.ws_connect(url)
        print("Connected! Waiting for pairs data...")

        # First message is "latestBlock", pairs data comes in subsequent messages
        raw_bytes = None
        for attempt in range(5):
            data = await ws.recv()
            if not data:
                continue
            msg = data[0]
            if b'pairs' in msg:
                raw_bytes = msg
                break
            print(f"  Skipping message #{attempt+1} ({len(msg)} bytes - not pairs data)")

        await ws.close()

        if not raw_bytes:
            print("No pairs data received")
            return []

        print(f"Received {len(raw_bytes)} bytes of pairs data")

        # Decode: replace non-printable with space
        decoded_text = ''.join(chr(b) if 32 <= b <= 126 else ' ' for b in raw_bytes)

        # Extract long words (potential addresses)
        words = [w for w in decoded_text.split() if len(w) >= 40]

        # Extract token addresses
        extracted_tokens = []
        for token in words:
            token_lower = token.lower()

            # Skip URLs
            if any(substr in token_lower for substr in ["https", "http", "//", ".com", ".site", ".xyz"]):
                continue

            # ETH addresses (0x...)
            if "0x" in token_lower:
                eth_match = re.findall(r'0x[0-9a-fA-F]{40}', token)
                if eth_match:
                    extracted_tokens.append(eth_match[-1])
                    continue

            # Pump tokens (Solana pump.fun)
            if "pump" in token_lower:
                pump_match = re.search(r'[A-Za-z0-9]{30,44}pump', token, re.IGNORECASE)
                if pump_match:
                    extracted_tokens.append(pump_match.group(0))
                    continue

            # Solana-like addresses (base58, 32-44 chars)
            candidate = token[-44:]
            if candidate.startswith('V'):
                candidate = candidate[1:]
            if re.match(r'^[A-HJ-NP-Za-km-z1-9]{32,44}$', candidate):
                extracted_tokens.append(candidate)

        # Remove duplicates while preserving order
        seen = set()
        unique_tokens = []
        for t in extracted_tokens:
            if t not in seen:
                seen.add(t)
                unique_tokens.append(t)

        return unique_tokens[:50]

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        await session.close()


def get_token_info(addresses):
    """Fetch token info from DexScreener API"""
    base_url = "https://api.dexscreener.com/latest/dex/tokens/"
    results = []

    for addr in addresses[:20]:  # Limit to avoid rate limits
        try:
            response = requests.get(f"{base_url}{addr}", timeout=10)
            if response.status_code == 200:
                data = response.json()
                pairs = data.get('pairs', [])
                if pairs:
                    pair = pairs[0]
                    results.append({
                        'address': addr,
                        'name': pair.get('baseToken', {}).get('name', 'Unknown'),
                        'symbol': pair.get('baseToken', {}).get('symbol', 'Unknown'),
                        'chain': pair.get('chainId', 'unknown'),
                        'price_usd': pair.get('priceUsd', 'N/A'),
                        'volume_24h': pair.get('volume', {}).get('h24', 0),
                        'price_change_24h': pair.get('priceChange', {}).get('h24', 0),
                        'url': pair.get('url', '')
                    })
        except Exception as e:
            print(f"Error fetching {addr[:20]}...: {e}")

    return results


async def main():
    # Get trending token addresses from WebSocket
    addresses = await get_trending_tokens()
    print(f"\nExtracted {len(addresses)} token addresses")

    if not addresses:
        return

    print("\nFirst 10 addresses:")
    for i, addr in enumerate(addresses[:10]):
        print(f"  {i+1}. {addr}")

    # Fetch detailed info from API
    print("\nFetching token details from DexScreener API...")
    tokens = get_token_info(addresses)

    print("\n" + "="*80)
    print("TRENDING TOKENS")
    print("="*80)
    print(f"{'Symbol':<12} {'Name':<25} {'Chain':<10} {'Price':<15} {'24h %':<10}")
    print("-"*80)

    for t in tokens:
        price = f"${t['price_usd']}" if t['price_usd'] != 'N/A' else 'N/A'
        change = f"{t['price_change_24h']}%" if t['price_change_24h'] else 'N/A'
        print(f"{t['symbol']:<12} {t['name'][:24]:<25} {t['chain']:<10} {price:<15} {change:<10}")

    # Save to JSON
    with open('trending_tokens.json', 'w') as f:
        json.dump(tokens, f, indent=2)
    print(f"\nSaved {len(tokens)} tokens to trending_tokens.json")


if __name__ == "__main__":
    asyncio.run(main())
