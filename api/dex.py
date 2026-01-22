import asyncio
import base64
import os
from curl_cffi.requests import AsyncSession
import json
import nest_asyncio
from datetime import datetime
import time
import struct
from decimal import Decimal, ROUND_DOWN
import re
import requests

# Apply nest_asyncio
nest_asyncio.apply()

Api = "TG bot API here"
ID = "Channel ID"

class DexBot():
    def __init__(self, api_key, url, channel_id=ID, max_token=10):
        self.api_key = api_key
        self.channel_id = channel_id
        self.max_token = max_token
        self.url = url
        

    def generate_sec_websocket_key(self):
        random_bytes = os.urandom(16)
        key = base64.b64encode(random_bytes).decode('utf-8')
        return key

    def get_headers(self):
        headers = {
            "Host": "io.dexscreener.com",
            "Connection": "Upgrade",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Upgrade": "websocket",
            "Origin": "https://dexscreener.com",
            'Sec-WebSocket-Version': '13',
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Sec-WebSocket-Key": self.generate_sec_websocket_key()
        }
        return headers

    def format_token_data(self):
        """
        Fetch information about specific tokens from the Dexscreener API.
        Uses async parallel requests in batches of 5 for speed.

        Returns:
            dict: A dictionary containing data for each token address or an error message.
        """
        token_addresses = self.start()

        # Run async fetching
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(self._fetch_tokens_async(token_addresses))
        loop.close()

        return json.dumps({"data": results}, indent=2)

    async def _fetch_single_token(self, session, address):
        """Fetch a single token's data"""
        base_url = "https://api.dexscreener.com/latest/dex/tokens/"
        try:
            response = await session.get(f"{base_url}{address}")
            if response.status_code == 200:
                data = response.json()
                pairs = data.get('pairs', [])
                if pairs and len(pairs) > 0:
                    return pairs[0]
                else:
                    return {"pairAddress": address, "Error": "No data Retrieved"}
            else:
                return {"pairAddress": address, "Error": f"Status code {response.status_code}"}
        except Exception as e:
            return {"pairAddress": address, "Error": f"Request error: {str(e)}"}

    async def _fetch_tokens_async(self, token_addresses, batch_size=10):
        """Fetch all tokens in parallel batches"""
        results = []
        async with AsyncSession(impersonate='chrome') as session:
            # Process in batches of 5
            for i in range(0, len(token_addresses), batch_size):
                batch = token_addresses[i:i + batch_size]
                print(f"Fetching batch {i//batch_size + 1}/{(len(token_addresses) + batch_size - 1)//batch_size} ({len(batch)} tokens)...")

                # Fetch batch in parallel
                tasks = [self._fetch_single_token(session, addr) for addr in batch]
                batch_results = await asyncio.gather(*tasks)
                results.extend(batch_results)

        return results
      

    async def connect(self):
        headers = self.get_headers()
        try:
            session = AsyncSession(headers=headers, impersonate='chrome')
            ws = await session.ws_connect(self.url)
            print(self.url)

            # Loop to keep receiving data until the connection is closed
            while True:
                try:
                    # Receive data from WebSocket
                    data = await ws.recv()

                    if data:
                        response = data[0]  # Assuming the first element contains the desired message
                        # Process and return the data or handle it as needed
                        #print(response)  # You can replace this with your desired processing logic
                        if "pairs" in str(response):
                          return response

                    else:
                        # If no data is received, break out of the loop
                        print("No data received.")
                        break

                except Exception as e:
                    print(f"Error receiving message: {str(e)}")
                    break

            # Closing the WebSocket and session after the loop ends
            await ws.close()
            await session.close()

        except Exception as e:
            print(f"Connection error: {str(e)}")
            return f"Connection error: {str(e)}"


    def tg_send(self, message):
        try:
            self.bot.send_message(self.channel_id, message, parse_mode='MarkdownV2', disable_web_page_preview=True)
        except Exception as e:
            print(f"Telegram sending error: {e}")



    def start(self):
        # Run the async connection
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        mes = loop.run_until_complete(self.connect())
        loop.close()

        # Decode message, replacing non-printable characters with space
        decoded_text = ''.join(chr(b) if 32 <= b <= 126 else ' ' for b in mes)

        # Split into long words
        words = [w for w in decoded_text.split() if len(w) >= 65]


        extracted_tokens = []

        for token in words:
            try:
                token_lower = token.lower()

                # Skip URLs
                if any(substr in token_lower for substr in ["https", "http", "//", ".com"]):
                    continue

                # ETH addresses
                if "0x" in token_lower:
                    eth_match = re.findall(r'0x[0-9a-fA-F]{40,}', token)
                    if eth_match:
                        extracted_tokens.append(eth_match[-1])
                        continue

                # Pump tokens
                if "pump" in token_lower:
                    pump_match = re.search(r'.{0,40}pump', token, re.IGNORECASE)
                    if pump_match:
                        extracted_tokens.append(pump_match.group(0).lstrip('V'))
                        continue

                # Bonk tokens
                if "bonk" in token_lower:
                    bonk_match = re.search(r'.{0,40}bonk', token, re.IGNORECASE)
                    if bonk_match.startswith('V'):
                        bonk_match = sol_token[1:]
                    if bonk_match:
                        extracted_tokens.append(bonk_match.group(0))
                        continue

                # Solana-like addresses (last 44 chars)
                sol_token = token[-44:]
                if sol_token.startswith('V'):
                    sol_token = sol_token[1:]
                extracted_tokens.append(sol_token)

            except Exception as e:
                print(f"Error processing token '{token}': {e}")


        print("Extraction complete")
        return extracted_tokens[:70]






    def token_getter(self, message):
        pass



