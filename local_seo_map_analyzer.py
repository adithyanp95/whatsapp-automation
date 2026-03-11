from playwright.sync_api import sync_playwright
import pandas as pd
import re
import math

# ─── CONFIG ────────────────────────────────────────────────────────────────────

KEYWORD       = "massage spa in calicut"
RESULT_LIMIT  = 10

# Option A: Search from a specific coordinate you provide
SEARCH_LAT  = 11.44380527815753     # e.g. a point ~10km from Calicut city center
SEARCH_LNG  = 75.70511156617809


# Option B: Calculate a point X km away from a base location
# Uncomment and set these to auto-compute SEARCH_LAT / SEARCH_LNG
# BASE_LAT      = 11.2588   # your actual location
# BASE_LNG      = 75.7804
# DISTANCE_KM   = 10        # how far away to simulate
# DIRECTION_DEG = 90        # compass bearing: 0=North, 90=East, 180=South, 270=West
# SEARCH_LAT, SEARCH_LNG = offset_coordinate(BASE_LAT, BASE_LNG, DISTANCE_KM, DIRECTION_DEG)

# ───────────────────────────────────────────────────────────────────────────────


def offset_coordinate(lat, lng, distance_km, bearing_deg):
    """
    Returns a new (lat, lng) that is `distance_km` away from the
    given point in the direction of `bearing_deg` (0=N, 90=E, 180=S, 270=W).
    Useful to simulate a customer 10km east/north/etc of your shop.
    """
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


def scrape_from_location(keyword, lat, lng, limit=5):
    results = []

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=False)

        # ── Inject fake GPS location ──────────────────────────────────────────
        context = browser.new_context(
            permissions=["geolocation"],
            geolocation={"latitude": lat, "longitude": lng, "accuracy": 10},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )
        page = context.new_page()

        print(f"\n📍 Simulating search from: {lat}, {lng}")
        print(f"🔍 Keyword: '{keyword}'\n")

        # @lat,lng,zoom in the URL pins the map view to the spoofed location
        maps_url = (
            f"https://www.google.com/maps/search/{keyword.replace(' ', '+')}/"
            f"@{lat},{lng},14z"
        )
        page.goto(maps_url, wait_until="domcontentloaded")

        try:
            page.wait_for_selector("a.hfpxzc", timeout=15000)
        except:
            print("⚠️  No listings found — try a different keyword or location.")
            browser.close()
            return results

        # Scroll results panel to load more listings
        for _ in range(3):
            panel = page.locator("div[role='feed']").first
            panel.evaluate("el => el.scrollBy(0, 2000)")
            page.wait_for_timeout(1000)

        # Collect listing URLs
        place_links = []
        for listing in page.locator("a.hfpxzc").all():
            href = listing.get_attribute("href")
            if href and "/place/" in href:
                place_links.append(href)
            if len(place_links) >= limit:
                break

        print(f"Collected {len(place_links)} listings. Scraping...\n")

        for idx, url in enumerate(place_links, 1):

            page.goto(url, wait_until="domcontentloaded")
            try:
                page.wait_for_selector("h1.DUwDvf", timeout=8000)
            except:
                pass

            # Name
            try:
                name = page.locator("h1.DUwDvf").inner_text(timeout=5000)
            except:
                name = "N/A"

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
                "Rank":      idx,
                "Name":      name,
                "Rating":    rating,
                "Reviews":   reviews,
                "Category":  category,
                "Address":   address,
                "Website":   website,
                "SearchLat": lat,
                "SearchLng": lng,
            })

            print(f"  #{idx} ✓ {name}  |  ⭐ {rating}  |  💬 {reviews}  |  🏷 {category}")

        browser.close()

    return results


# ── SINGLE LOCATION RUN ────────────────────────────────────────────────────────

results = scrape_from_location(KEYWORD, SEARCH_LAT, SEARCH_LNG, RESULT_LIMIT)

df = pd.DataFrame(results)
print("\n── Final Results ─────────────────────────────────────────────────────────")
print(df[["Rank", "Name", "Rating", "Reviews", "Category", "Address"]].to_string(index=False))
df.to_csv("local_businesses.csv", index=False)
print("\n✅ Saved to local_businesses.csv")


# ── GRID / MULTI-POINT SCAN (uncomment to run) ────────────────────────────────
# Simulates searches from a ring of points around a base location.
# Great for local SEO rank tracking — see how your business ranks
# as a customer moves further away in any direction.
#
# BASE_LAT, BASE_LNG = 11.2588, 75.7804
# GRID_POINTS = [
#     offset_coordinate(BASE_LAT, BASE_LNG, km, deg)
#     for km, deg in [(0, 0), (5, 0), (5, 90), (5, 180), (5, 270),
#                     (10, 0), (10, 90), (10, 180), (10, 270)]
# ]
#
# all_results = []
# for lat, lng in GRID_POINTS:
#     all_results.extend(scrape_from_location(KEYWORD, lat, lng, RESULT_LIMIT))
#
# df_grid = pd.DataFrame(all_results)
# df_grid.to_csv("grid_rank_tracker.csv", index=False)
# print("✅ Grid scan saved to grid_rank_tracker.csv")
