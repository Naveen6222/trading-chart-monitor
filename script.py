import asyncio
import requests
import os
import sys
from playwright.async_api import async_playwright
from google import genai

# ==========================================
# CONFIGURATION
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") 

if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY environment variable not set.")
    sys.exit(1)

# 1. Type the exact word you subscribed to in the ntfy app here
NTFY_TOPIC = "forex_notification" 

# 2. Dictionary containing all 6 of your specific TradingView chart URLs
CHARTS = {
    "EURUSD": "https://in.tradingview.com/chart/Ykp2GGtJ/?symbol=FX%3AEURUSD",
    "GBPUSD": "https://in.tradingview.com/chart/Ykp2GGtJ/?symbol=FX%3AGBPUSD",
    "NZDUSD": "https://in.tradingview.com/chart/Ykp2GGtJ/?symbol=FX%3ANZDUSD",
    "AUDUSD": "https://in.tradingview.com/chart/Ykp2GGtJ/?symbol=FX%3AAUDUSD",
    "USDJPY": "https://in.tradingview.com/chart/Ykp2GGtJ/?symbol=FX%3AUSDJPY",
    "USDCAD": "https://in.tradingview.com/chart/Ykp2GGtJ/?symbol=FX%3AUSDCAD"
}

# Initialize Gemini Client
client = genai.Client(api_key=GEMINI_API_KEY)

async def check_all_charts():
    positive_setups = []
    
    print("Launching browser...")
    async with async_playwright() as p:
        # Open one browser session to handle all 6 charts
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        
        for pair, url in CHARTS.items():
            print(f"Checking {pair}...")
            
            # Navigate to the chart
            await page.goto(url, wait_until="domcontentloaded")
            
            # Wait 5 seconds for chart data and indicators to fully render
            await page.wait_for_timeout(5000)
            
            # Capture the screenshot
            screenshot_path = f"{pair}.png"
            await page.screenshot(path=screenshot_path)
            
            # Upload to Gemini
            image_file = client.files.upload(file=screenshot_path)
            
            # Request strict YES/NO analysis
            prompt = f"""
            You are a strict technical analysis assistant. Look at this {pair} chart.
            Does it currently show a highly favorable setup for a breakout?
            Answer with ONLY the word "YES" or "NO". Do not provide any other text.
            """
            
            # Using the Flash model to stay within the 1,500 RPD free tier limit
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=[prompt, image_file]
            )
            
            result_text = response.text.strip().upper()
            print(f"{pair} Gemini concluded: {result_text}")
            
            # If the model says YES, add the pair to our notification list
            if "YES" in result_text:
                positive_setups.append(pair)
                
        # Close the browser once all charts are checked
        await browser.close()
        
    # Trigger a single phone notification if any charts triggered a YES
    if positive_setups:
        print(f"Triggering phone notification for {len(positive_setups)} setups...")
        
        # Join the list of pairs into a readable string (e.g., "EURUSD, GBPUSD")
        pairs_string = ", ".join(positive_setups)
        
        requests.post(
            f"https://ntfy.sh/forex_notification", 
            data=f"Gemini says YES for: {pairs_string}! Check your charts.",
            headers={"Title": "Gemini Breakout Alert", "Priority": "high"}
        )
    else:
        print("No action required this time.")

if __name__ == "__main__":
    print("Starting automated 6-chart cloud check...")
    asyncio.run(check_all_charts())
    print("Check complete.")
