from playwright.sync_api import sync_playwright
import time
import re

LABEL_NAME = "SEO&GAds"

date_pattern = r"\d{1,2}/\d{1,2}/\d{4}"

with sync_playwright() as p:

    browser = p.chromium.launch_persistent_context(
        user_data_dir="whatsapp_session",
        headless=False
    )

    page = browser.pages[0] if browser.pages else browser.new_page()

    page.goto("https://web.whatsapp.com")

    print("Waiting for WhatsApp to load...")
    time.sleep(8)

    # open label filter
    page.click("text=Labels")
    time.sleep(2)

    # select the label
    page.locator("text=" + LABEL_NAME).click()
    time.sleep(5)

    chats = page.query_selector_all("div[role='row']")
    print("Total leads in label:", len(chats))
    print()

    for chat in chats:

        row_text = chat.inner_text()

        # extract date
        match = re.search(date_pattern, row_text)
        last_message_date = match.group(0) if match else "Unknown"

        # extract name / phone
        lead = row_text.split("\n")[0]

        print("Lead:", lead)
        print("Last Message Date:", last_message_date)
        print("------")

    print("Finished extracting leads from label:", LABEL_NAME)

    browser.close()