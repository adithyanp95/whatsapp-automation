from playwright.sync_api import sync_playwright
import pandas as pd
import re
import math

# ─── CONFIG ────────────────────────────────────────────────────────────────────

KEYWORD         = "massage spa near me"
TARGET_BUSINESS = "Orange Wellness Spa & Salon Calicut"   # exact (or partial) name to track
RESULT_LIMIT    = 10                           # scan top 10 per point to find rank

# Your business location as the CENTER of the grid
CENTER_LAT = 11.358450667017733 
CENTER_LNG = 75.78683404681983

GRID_SIZE   = 5    # 5x5
STEP_KM     = 1.0  # 1 km between each grid point

# ───────────────────────────────────────────────────────────────────────────────

# Terminal colors
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
GRAY   = "\033[90m"
BOLD   = "\033[1m"
RESET  = "\033[0m"
CYAN   = "\033[96m"


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


def build_grid(center_lat, center_lng, size, step_km):
    """
    Returns a 2D list [row][col] of (lat, lng).
    Row 0 = northernmost, Col 0 = westernmost.
    Center cell = (size//2, size//2).
    """
    half = size // 2
    grid = []
    for row in range(size):
        north_offset = (half - row) * step_km      # positive = north
        lat, _ = offset_coordinate(center_lat, center_lng, abs(north_offset),
                                   0 if north_offset >= 0 else 180)
        grid_row = []
        for col in range(size):
            east_offset = (col - half) * step_km   # positive = east
            _, lng = offset_coordinate(lat, center_lng, abs(east_offset),
                                       90 if east_offset >= 0 else 270)
            grid_row.append((lat, lng))
        grid.append(grid_row)
    return grid


def extract_number(text):
    cleaned = text.replace(",", "").replace(".", "")
    nums = re.findall(r'\d+', cleaned)
    return int(nums[0]) if nums else 0


def extract_rating(text):
    match = re.search(r'(\d+[.,]\d+)', text)
    return float(match.group().replace(",", ".")) if match else 0.0


def rank_color(rank):
    if rank is None:
        return f"{GRAY}[N/F]{RESET}"
    if rank <= 3:
        return f"{GREEN}{BOLD}[#{rank}]{RESET}"
    elif rank <= 6:
        return f"{YELLOW}[#{rank}]{RESET}"
    else:
        return f"{RED}[#{rank}]{RESET}"


def scrape_rank_at(page, keyword, lat, lng, target, limit):
    """Navigate to a grid point and return the rank of `target` business."""

    maps_url = (
        f"https://www.google.com/maps/search/{keyword.replace(' ', '+')}/"
        f"@{lat},{lng},14z"
    )
    page.goto(maps_url, wait_until="domcontentloaded")

    try:
        page.wait_for_selector("a.hfpxzc", timeout=12000)
    except:
        return None

    # Scroll to load enough results
    for _ in range(3):
        try:
            panel = page.locator("div[role='feed']").first
            panel.evaluate("el => el.scrollBy(0, 2000)")
            page.wait_for_timeout(800)
        except:
            break

    listings = page.locator("a.hfpxzc").all()
    target_lower = target.lower()

    for idx, listing in enumerate(listings[:limit], 1):
        name = listing.get_attribute("aria-label") or ""
        if target_lower in name.lower():
            return idx

    return None  # not found in top `limit`


def print_grid(grid_ranks, size, step_km):
    half = size // 2
    cell_w = 6  # chars per cell

    print(f"\n{BOLD}{'─'*60}{RESET}")
    print(f"{BOLD}  📍 5×5 RANK GRID  —  {TARGET_BUSINESS}{RESET}")
    print(f"  Center: {CENTER_LAT}, {CENTER_LNG}  |  Step: {step_km} km")
    print(f"{BOLD}{'─'*60}{RESET}")

    # Column header (W … Center … E)
    header = "       "
    for col in range(size):
        offset = col - half
        if offset == 0:
            label = " CTR "
        elif offset < 0:
            label = f"W{abs(offset)*step_km:.0f}km"
        else:
            label = f"E{offset*step_km:.0f}km"
        header += f"{label:^7}"
    print(header)
    print()

    for row in range(size):
        offset = half - row
        if offset == 0:
            row_label = " CTR "
        elif offset > 0:
            row_label = f"N{offset*step_km:.0f}km "
        else:
            row_label = f"S{abs(offset)*step_km:.0f}km "

        row_str = f"  {BOLD}{row_label}{RESET} "
        for col in range(size):
            rank = grid_ranks[row][col]
            cell = rank_color(rank)
            row_str += f"  {cell} "
        print(row_str)
        print()

    # Legend
    print(f"  Legend:  {GREEN}{BOLD}[#1-3]{RESET} Top 3   "
          f"{YELLOW}[#4-6]{RESET} Mid   "
          f"{RED}[#7+]{RESET} Low   "
          f"{GRAY}[N/F]{RESET} Not found in top {RESULT_LIMIT}")
    print(f"{BOLD}{'─'*60}{RESET}\n")


# ── BUILD GRID ─────────────────────────────────────────────────────────────────

grid_coords = build_grid(CENTER_LAT, CENTER_LNG, GRID_SIZE, STEP_KM)
grid_ranks  = [[None] * GRID_SIZE for _ in range(GRID_SIZE)]
total_points = GRID_SIZE * GRID_SIZE

print(f"\n{BOLD}🗺  Starting 5×5 grid scan ({total_points} points){RESET}")
print(f"   Tracking: {CYAN}{TARGET_BUSINESS}{RESET}")
print(f"   Keyword:  {KEYWORD}")
print(f"   Center:   {CENTER_LAT}, {CENTER_LNG}\n")

with sync_playwright() as p:

    browser = p.chromium.launch(headless=True)   # headless=True = faster, no window
    context = browser.new_context(
        permissions=["geolocation"],
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 800},
        locale="en-US",
    )
    page = context.new_page()

    done = 0
    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            lat, lng = grid_coords[row][col]
            done += 1

            # Update geolocation for each point
            context.set_geolocation({"latitude": lat, "longitude": lng, "accuracy": 10})

            rank = scrape_rank_at(page, KEYWORD, lat, lng, TARGET_BUSINESS, RESULT_LIMIT)
            grid_ranks[row][col] = rank

            rank_str = f"#{rank}" if rank else "N/F"
            half = GRID_SIZE // 2
            r_off = half - row
            c_off = col - half
            pos = (
                f"{'N' if r_off>0 else 'S'}{abs(r_off)}km, {'E' if c_off>=0 else 'W'}{abs(c_off)}km"
                if not (r_off == 0 and c_off == 0) else "CENTER"
            )
            print(f"  [{done:2}/{total_points}]  {pos:<16}  ({lat}, {lng})  →  {rank_str}")

    browser.close()

# ── PRINT HEATMAP ──────────────────────────────────────────────────────────────

print_grid(grid_ranks, GRID_SIZE, STEP_KM)

# ── SAVE CSV ───────────────────────────────────────────────────────────────────

rows = []
half = GRID_SIZE // 2
for row in range(GRID_SIZE):
    for col in range(GRID_SIZE):
        lat, lng = grid_coords[row][col]
        rows.append({
            "row": row, "col": col,
            "lat": lat, "lng": lng,
            "north_km": (half - row) * STEP_KM,
            "east_km":  (col - half) * STEP_KM,
            "rank": grid_ranks[row][col],
        })

df = pd.DataFrame(rows)
df.to_csv("grid_ranks.csv", index=False)
print("✅  Saved to grid_ranks.csv\n")