from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch_persistent_context(
        user_data_dir="whatsapp_session",
        headless=False
    )

    page = browser.pages[0] if browser.pages else browser.new_page()

    page.goto("https://web.whatsapp.com")

    input("Scan QR once, then press ENTER")

    print("Session saved. Next time QR will not be required.")

    browser.close()