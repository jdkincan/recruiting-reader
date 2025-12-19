from src.utils.utils import body_text
from src.scraper.data_extractors import open_timeline, parse_timeline_events, timeline_lines


def test_timeline(driver, player_url):
    driver.get(player_url)

    ok = open_timeline(driver, tries=3)
    if not ok:
        raise RuntimeError("Timeline did not load date lines after retries")

    events = parse_timeline_events(
        timeline_lines(body_text(driver))
    )

    for e in events[:10]:
        print(e.date.strftime("%Y-%m-%d"), e.kind, "|", e.text)

    return events