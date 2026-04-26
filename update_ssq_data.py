#!/usr/bin/env python3

import json
import re
import ssl
import urllib.request
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LATEST_JSON = ROOT / "latest_1.json"
HISTORY_JSON = ROOT / "history_1.json"

XML_URL = "https://kaijiang.500.com/static/info/kaijiang/xml/ssq/list.xml"
HTML_URL = (
    "https://datachart.500.com/ssq/history/newinc/history.php?start=03001&end=99999"
)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    context = ssl.create_default_context()
    with urllib.request.urlopen(request, timeout=30, context=context) as response:
        content = response.read()
    return content.decode("utf-8", "ignore")


def fetch_draws_from_xml() -> list[dict]:
    text = fetch_text(XML_URL)
    rows = re.findall(
        r'<row\s+expect="(\d+)"\s+opencode="([0-9,|]+)"\s+opentime="([0-9:\- ]+)"', text
    )
    draws = []
    for issue, open_code, open_time in rows:
        reds, blue = open_code.split("|")
        draws.append(
            {
                "issue": issue,
                "drawDate": open_time,
                "redBalls": [int(x) for x in reds.split(",")],
                "blueBall": int(blue),
            }
        )
    if not draws:
        raise RuntimeError("XML 数据源没有解析到开奖数据")
    return sorted(draws, key=lambda item: item["issue"], reverse=True)


def fetch_draws_from_html() -> list[dict]:
    text = fetch_text(HTML_URL).replace("\n", "").replace("\r", "")
    pattern = re.compile(
        r'<tr class="t_tr\d+">.*?<td>(\d{5})</td><td class="t_cfont2">(\d+)</td><td class="t_cfont2">(\d+)</td><td class="t_cfont2">(\d+)</td><td class="t_cfont2">(\d+)</td><td class="t_cfont2">(\d+)</td><td class="t_cfont2">(\d+)</td><td class="t_cfont4">(\d+)</td>.*?<td>(\d{4}-\d{2}-\d{2})</td>'
    )
    draws = []
    for match in pattern.finditer(text):
        issue = match.group(1)
        reds = [int(match.group(i)) for i in range(2, 8)]
        blue = int(match.group(8))
        draw_date = match.group(9) + " 21:15:00"
        draws.append(
            {
                "issue": issue,
                "drawDate": draw_date,
                "redBalls": reds,
                "blueBall": blue,
            }
        )
    if not draws:
        raise RuntimeError("HTML 备用源没有解析到开奖数据")
    return sorted(draws, key=lambda item: item["issue"], reverse=True)


def fetch_draws() -> tuple[list[dict], str]:
    try:
        return fetch_draws_from_xml(), "500-xml"
    except Exception:
        return fetch_draws_from_html(), "500-html"


def build_latest_announcement(latest_draw: dict) -> dict:
    issue = latest_draw["issue"]
    detail_url = f"https://datachart.500.com/ssq/history/newinc/history.php?start={issue}&end={issue}"
    text = fetch_text(detail_url).replace("\n", "").replace("\r", "")
    pattern = re.compile(
        r'<tr class="t_tr1">.*?<td>(\d+)</td><td class="t_cfont2">\d+</td><td class="t_cfont2">\d+</td><td class="t_cfont2">\d+</td><td class="t_cfont2">\d+</td><td class="t_cfont2">\d+</td><td class="t_cfont2">\d+</td><td class="t_cfont4">\d+</td><td class="t_cfont4">.*?</td><td>([\d,]+)</td><td>(\d+)</td><td>([\d,]+)</td><td>(\d+)</td><td>([\d,]+)</td><td>([\d,]+)</td><td>(\d{4}-\d{2}-\d{2})</td>'
    )
    match = pattern.search(text)
    if not match:
        return {
            "issue": issue,
            "drawDate": latest_draw["drawDate"][:10],
            "salesAmount": 0,
            "jackpotAmount": 0,
            "firstPrizeCount": 0,
            "firstPrizeAmount": 0,
            "secondPrizeCount": 0,
            "secondPrizeAmount": 0,
        }
    return {
        "issue": match.group(1),
        "jackpotAmount": int(match.group(2).replace(",", "")),
        "firstPrizeCount": int(match.group(3)),
        "firstPrizeAmount": int(match.group(4).replace(",", "")),
        "secondPrizeCount": int(match.group(5)),
        "secondPrizeAmount": int(match.group(6).replace(",", "")),
        "salesAmount": int(match.group(7).replace(",", "")),
        "drawDate": match.group(8),
    }


def main() -> None:
    draws, source = fetch_draws()
    latest_draw = draws[0]
    latest_announcement = build_latest_announcement(latest_draw)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    latest_payload = {
        "source": source,
        "updatedAt": now,
        "latestIssue": latest_draw["issue"],
        "latestAnnouncement": latest_announcement,
        "latestDraw": latest_draw,
    }
    history_payload = {
        "source": source,
        "updatedAt": now,
        "latestIssue": latest_draw["issue"],
        "totalCount": len(draws),
        "latestAnnouncement": latest_announcement,
        "draws": draws,
    }

    LATEST_JSON.write_text(
        json.dumps(latest_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    HISTORY_JSON.write_text(
        json.dumps(history_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"updated latest issue: {latest_draw['issue']}")
    print(f"source: {source}")
    print(f"history count: {len(draws)}")


if __name__ == "__main__":
    main()
