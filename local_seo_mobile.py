from playwright.sync_api import sync_playwright
import pandas as pd
import re
import math

# ─── CONFIG ────────────────────────────────────────────────────────────────────

KEYWORD       = "massage spa in calicut"
RESULT_LIMIT  = 10

SEARCH_LAT  = 11.357510859603991
SEARCH_LNG  = 75.78689942311941

# ───────────────────────────────────────────────────────────────────────────────


def offset_coordinate(lat, lng, distance_km, bearing_deg):
    R = 6371.0
    bearing = math.radians(bearing_deg)
    lat1 = math.radians(lat)
    lng1 = math.radians(lng)
    lat2 = math.asin(
        math.sin(lat1) * math.cos(distance_km / R) +
        math.cos(lat1) * math.sin(distance_km / R) * math.cos(bearing)
    )
    lng2 = lng1 + math.atan2(
        math.sin(bearing) * math.sin(distance_km / R) * math.cos(lat1),
        math.cos(distance_km / R) - math.sin(lat1) * math.sin(lat2)
    )
    return round(math.degrees(lat2), 6), round(math.degrees(lng2), 6)


def extract_number(text):
    cleaned = text.replace(",", "").replace(".", "")
    nums = re.findall(r'\d+', cleaned)
    return int(nums[0]) if nums else 0


def extract_rating(text):
    match = re.search(r'(\d+[.,]\d+)', text)
    if match:
        return float(match.group().replace(",", "."))
    return 0.0


def get_maps_url(keyword, lat, lng):
    return (
        f"https://www.google.com/maps/search/{keyword.replace(' ', '+')}/"
        f"@{lat},{lng},14z"
    )


def dismiss_popup(page):
    try:
        btn = page.locator("button:has-text('Go back to web')")
        btn.wait_for(state="visible", timeout=4000)
        btn.click()
        print("  ✅ Dismissed popup")
        page.wait_for_timeout(1500)
        return True
    except:
        return False


def scrape_from_location(keyword, lat, lng, limit=10):
    results = []
    maps_url = get_maps_url(keyword, lat, lng)

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            permissions=["geolocation"],
            geolocation={"latitude": lat, "longitude": lng, "accuracy": 10},
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                "Mobile/15E148 Safari/604.1"
            ),
            viewport={"width": 390, "height": 844},
            is_mobile=True,
            has_touch=True,
            locale="en-US",
        )
        page = context.new_page()

        print(f"\n📍 Simulating search from: {lat}, {lng}")
        print(f"📱 Device: iPhone 14 (mobile)")
        print(f"🔍 Keyword: '{keyword}'\n")

        page.goto(maps_url, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)

        # Dismiss popup then reload the search URL
        if dismiss_popup(page):
            print("  🔄 Reloading search results...")
            page.goto(maps_url, wait_until="domcontentloaded")
            page.wait_for_timeout(2500)

        # Wait for mobile listing cards (button.hfpxzc inside div.Nv2PK)
        try:
            page.wait_for_selector("div.Nv2PK", timeout=12000)
        except:
            print("⚠️  No listings found.")
            browser.close()
            return results

        # Scroll to load more cards
        for _ in range(3):
            try:
                page.evaluate("window.scrollBy(0, 2000)")
                page.wait_for_timeout(1000)
            except:
                break

        # Collect all card aria-labels (business names) to iterate by index
        cards = page.locator("div.Nv2PK").all()
        total = min(len(cards), limit)
        print(f"  Found {len(cards)} listing cards. Scraping top {total}...\n")

        for idx in range(total):

            # Re-query cards each time since DOM refreshes after back navigation
            page.goto(maps_url, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            dismiss_popup(page)

            try:
                page.wait_for_selector("div.Nv2PK", timeout=10000)
            except:
                print(f"  ⚠️  Lost listings at card {idx+1}, stopping.")
                break

            cards = page.locator("div.Nv2PK").all()
            if idx >= len(cards):
                break

            card = cards[idx]

            # Get the name from aria-label before clicking
            pre_name = card.get_attribute("aria-label") or f"Business {idx+1}"

            # Click the button inside the card to open the detail page
            try:
                card.locator("button.hfpxzc").click()
            except:
                card.click()

            # Wait for detail page to load
            try:
                page.wait_for_selector("h1.DUwDvf", timeout=10000)
            except:
                pass

            page.wait_for_timeout(1500)

            # ── Scrape detail page ────────────────────────────────────────────

            # Name
            try:
                name = page.locator("h1.DUwDvf").inner_text(timeout=5000)
            except:
                name = pre_name  # fallback to aria-label

            # Rating
            rating = 0.0
            try:
                aria = page.locator("div.F7nice span[aria-hidden='true']").first.inner_text(timeout=4000)
                rating = extract_rating(aria)
            except:
                pass
            if rating == 0:
                try:
                    aria = page.locator("span.ceNzKf").get_attribute("aria-label", timeout=3000)
                    rating = extract_rating(aria or "")
                except:
                    pass

            # Reviews
            reviews = 0
            try:
                rev_text = page.locator("div.F7nice span[aria-label*='review']").inner_text(timeout=4000)
                reviews = extract_number(rev_text)
            except:
                pass
            if reviews == 0:
                try:
                    rev_text = page.locator("button[jsaction*='reviewChart']").inner_text(timeout=3000)
                    reviews = extract_number(rev_text)
                except:
                    pass

            # Category
            try:
                category = page.locator("button.DkEaL").first.inner_text(timeout=4000)
            except:
                try:
                    category = page.locator("span.YhemCb").first.inner_text(timeout=3000)
                except:
                    category = "N/A"

            # Address
            try:
                address = page.locator("button[data-item-id='address']").inner_text(timeout=4000)
                address = address.strip()
            except:
                try:
                    address = page.locator("[data-tooltip='Copy address']").inner_text(timeout=3000)
                except:
                    address = "N/A"

            # Website
            try:
                website = page.locator("a[data-item-id='authority']").get_attribute("href", timeout=4000)
            except:
                website = "N/A"

            results.append({
                "Rank":      idx + 1,
                "Name":      name,
                "Rating":    rating,
                "Reviews":   reviews,
                "Category":  category,
                "Address":   address,
                "Website":   website,
                "SearchLat": lat,
                "SearchLng": lng,
            })

            print(f"  #{idx+1} ✓ {name}  |  ⭐ {rating}  |  💬 {reviews}  |  🏷 {category}")

        browser.close()

    return results


# ── RUN ────────────────────────────────────────────────────────────────────────

results = scrape_from_location(KEYWORD, SEARCH_LAT, SEARCH_LNG, RESULT_LIMIT)

if results:
    df = pd.DataFrame(results)
    print("\n── Final Results ─────────────────────────────────────────────────────────")
    print(df[["Rank", "Name", "Rating", "Reviews", "Category", "Address"]].to_string(index=False))
    df.to_csv("local_businesses.csv", index=False)
    print("\n✅ Saved to local_businesses.csv")
else:
    print("\n⚠️  No results scraped.")
    print("   • Popup wasn't dismissed in time — try running again")
    print("   • Keyword returned no results at this location")
    print("   • Google temporarily blocked the request")