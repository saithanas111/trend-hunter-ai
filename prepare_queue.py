import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

REPORT = Path("trend_report.md")
QUEUE_JSON = Path("content_queue.json")
QUEUE_CSV = Path("content_queue.csv")


def clean(value):
    return re.sub(r"\\s+", " ", value or "").strip().strip("`*")


def extract(section, label):
    # Captions in the report are usually bold labels embedded in a numbered paragraph.
    patterns = [
        rf"(?im)^\\s*[-*]?\\s*\\*\\*{re.escape(label)}:\\*\\*\\s*(.+)$",
        rf"(?im)^\\s*\\d+\\.\\s*\\*\\*{re.escape(label)}:\\*\\*\\s*(.+)$",
        rf"(?im)^\\s*[-*]?\\s*{re.escape(label)}\\s*:\\s*(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, section)
        if match:
            return clean(match.group(1))
    return ""


def main():
    if not REPORT.exists():
        raise SystemExit("trend_report.md is missing; run main.py first.")
    report = REPORT.read_text(encoding="utf-8")
    matches = list(re.finditer(r"(?m)^## Opportunity\\s+(\\d+)\\s*:\\s*(.+)$", report))
    numbers = [int(match.group(1)) for match in matches]
    if numbers != list(range(1, 11)):
        raise SystemExit(f"Expected Opportunity 1 through 10 exactly once; found {numbers}")

    queue = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(report)
        section = report[match.end():end]
        affiliate = extract(section, "Affiliate URL")
        queue.append({
            "opportunity": int(match.group(1)),
            "product": clean(match.group(2)),
            "facebook_caption": extract(section, "Facebook Caption"),
            "instagram_caption": extract(section, "Instagram Caption"),
            "tiktok_hook": extract(section, "TikTok Hook"),
            "affiliate_url": affiliate if affiliate and "ADD VERIFIED" not in affiliate.upper() else "",
            "affiliate_status": "needs_verified_link" if not affiliate or "ADD VERIFIED" in affiliate.upper() else "link_supplied_not_validated",
            "publishing_status": "draft_not_published",
            "approval_required": True,
        })

    # Do not silently create an empty or incomplete queue.
    missing = [
        item["opportunity"] for item in queue
        if not item["facebook_caption"] or not item["instagram_caption"] or not item["tiktok_hook"]
    ]
    if missing:
        raise SystemExit(f"Missing required social copy for opportunities: {missing}")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(queue),
        "notice": "Draft queue only. Affiliate links must be verified and posts require connected, authorized publishing integration and approval.",
        "items": queue,
    }
    QUEUE_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with QUEUE_CSV.open("w", newline="", encoding="utf-8-sig") as handle:
        fields = ["opportunity", "product", "facebook_caption", "instagram_caption", "tiktok_hook", "affiliate_url", "affiliate_status", "publishing_status", "approval_required"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(queue)
    print(f"Prepared {len(queue)} complete draft opportunities in content_queue.json and content_queue.csv")


if __name__ == "__main__":
    main()
