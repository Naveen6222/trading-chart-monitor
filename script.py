import asyncio
import os
import sys
from google import genai
from playwright.async_api import async_playwright
import requests

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY environment variable not set.")
    sys.exit(1)

NTFY_TOPIC = "forex_notification"

CHARTS = {
    "EURUSD": "https://in.tradingview.com/chart/Ykp2GGtJ/?symbol=FX%3AEURUSD",
    "GBPUSD": "https://in.tradingview.com/chart/Ykp2GGtJ/?symbol=FX%3AGBPUSD",
    "NZDUSD": "https://in.tradingview.com/chart/Ykp2GGtJ/?symbol=FX%3ANZDUSD",
    "AUDUSD": "https://in.tradingview.com/chart/Ykp2GGtJ/?symbol=FX%3AAUDUSD",
    "USDJPY": "https://in.tradingview.com/chart/Ykp2GGtJ/?symbol=FX%3AUSDJPY",
    "USDCAD": "https://in.tradingview.com/chart/Ykp2GGtJ/?symbol=FX%3AUSDCAD",
}

client = genai.Client(api_key=GEMINI_API_KEY)


async def check_all_charts():
    positive_setups = []

    print("Launching browser...")
    async with async_playwright() as p:
        # User agent added to avoid bot detection blocks
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        page = await context.new_page()

        for pair, url in CHARTS.items():
            uploaded_file = None
            try:
                print(f"Checking {pair}...")
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(
                    8000
                )  # Allow TradingView canvas to draw indicators/candlesticks

                screenshot_path = f"{pair}.png"
                await page.screenshot(path=screenshot_path)

                # Upload image to Gemini API
                uploaded_file = client.files.upload(file=screenshot_path)

                prompt = f"""
                Analyze the provided raw chart solely to identify the Golden Strategy structure. 
                Respond with YES only if the {pair} chart strictly meets both core structural criteria: 
                (1) An aggressive, impulsive X-A leg showing strong institutional displacement/momentum, and 
                (2) A slow, choppy, corrective A-D return that exhausts directly into a key Order Block/Demand-Supply zone near Point D. 
                
                If the X-A leg is choppy/weak, the A-D return is overly aggressive, or the structure is ambiguous, respond with NO.
                Answer with ONLY the word "YES" or "NO". Do not provide any other text.
                """

                response = client.models.generate_content(
                    model="gemini-2.0-flash", contents=[prompt, uploaded_file]
                )

                result_text = response.text.strip().upper()
                print(f"{pair} Gemini concluded: {result_text}")

                if "YES" in result_text:
                    positive_setups.append(pair)

                # Clean up local screenshot file
                if os.path.exists(screenshot_path):
                    os.remove(screenshot_path)

            except Exception as e:
                print(f"Error processing {pair}: {e}")

            finally:
                # CRITICAL: Clean up file from Gemini Files API storage
                if uploaded_file:
                    try:
                        client.files.delete(name=uploaded_file.name)
                    except Exception as del_err:
                        print(f"Failed to delete remote file for {pair}: {del_err}")

        await browser.close()

    if positive_setups:
        print(
            f"Triggering phone notification for {len(positive_setups)} setups..."
        )
        pairs_string = ", ".join(positive_setups)
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=f"Gemini identified Golden Strategy for: {pairs_string}! Check your charts.",
            headers={"Title": "Golden Strategy Alert 🚀", "Priority": "high"},
        )
    else:
        print("No setups matched the criteria in this run.")


if __name__ == "__main__":
    print("Starting automated 6-chart cloud check...")
    asyncio.run(check_all_charts())
    print("Check complete.")
