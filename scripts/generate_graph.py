# scripts/generate_graph.py

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

USERNAME = os.environ.get("GITHUB_USERNAME", "aonontojahan")
TOKEN = os.environ.get("GITHUB_TOKEN")

if not TOKEN:
    raise RuntimeError("GITHUB_TOKEN is missing.")

API_URL = "https://api.github.com/search/commits"
OUTPUT = Path("assets/contribution-graph.svg")
DAYS = 30


def get_daily_commits(day):
    """Count commits authored by the user on a specific date."""
    query = f"author:{USERNAME} author-date:{day.isoformat()}"
    url = API_URL + "?" + urllib.parse.urlencode({"q": query, "per_page": 1})

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {TOKEN}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "daily-commit-graph",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.load(response)
            return int(data.get("total_count", 0))
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub API error for {day}: HTTP {error.code}: {details}"
        ) from error


def make_svg(labels, values):
    width, height = 1100, 430
    left, right, top, bottom = 70, 30, 45, 105
    plot_width = width - left - right
    plot_height = height - top - bottom

    maximum = max(values, default=0)
    y_max = max(5, ((maximum + 4) // 5) * 5)

    def x_position(index):
        if len(values) == 1:
            return left + plot_width / 2
        return left + index * plot_width / (len(values) - 1)

    def y_position(value):
        return top + plot_height - (value / y_max) * plot_height

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-labelledby="title desc">',
        '<title id="title">Daily GitHub Commit Progress</title>',
        '<desc id="desc">Daily commit counts for the last 30 days '
        f'for {escape(USERNAME)}.</desc>',
        '<rect width="100%" height="100%" fill="#FFFFFF"/>',
        '<style>',
        'text{font-family:Arial,Helvetica,sans-serif;fill:#6B7280}',
        '.grid{stroke:#D1D5DB;stroke-width:1}',
        '.axis{stroke:#666666;stroke-width:2}',
        '.line{fill:none;stroke:#48B7C2;stroke-width:4;'
        'stroke-linejoin:round;stroke-linecap:round}',
        '.point{fill:#FFFFFF;stroke:#48B7C2;stroke-width:3}',
        '</style>',
        '<text x="70" y="25" font-size="18" font-weight="600" '
        'fill="#374151">Daily GitHub Commit Progress</text>',
    ]

    # Horizontal gridlines and Y-axis labels.
    tick_step = max(1, y_max // 5)
    ticks = list(range(0, y_max + 1, tick_step))
    if ticks[-1] != y_max:
        ticks.append(y_max)

    for tick in ticks:
        y = y_position(tick)
        parts.append(
            f'<line class="grid" x1="{left}" y1="{y:.2f}" '
            f'x2="{width-right}" y2="{y:.2f}"/>'
        )
        parts.append(
            f'<text x="{left-15}" y="{y+5:.2f}" '
            f'text-anchor="end" font-size="13">{tick}</text>'
        )

    # Vertical gridlines and date labels, shown every other day.
    for index, label in enumerate(labels):
        if index % 2 == 0 or index == len(labels) - 1:
            x = x_position(index)
            parts.append(
                f'<line class="grid" x1="{x:.2f}" y1="{top}" '
                f'x2="{x:.2f}" y2="{top+plot_height}"/>'
            )
            parts.append(
                f'<text x="{x:.2f}" y="{top+plot_height+18}" '
                f'text-anchor="end" font-size="11" '
                f'transform="rotate(-45 {x:.2f} '
                f'{top+plot_height+18})">{escape(label)}</text>'
            )

    # Axes.
    parts.extend([
        f'<line class="axis" x1="{left}" y1="{top}" '
        f'x2="{left}" y2="{top+plot_height}"/>',
        f'<line class="axis" x1="{left}" y1="{top+plot_height}" '
        f'x2="{width-right}" y2="{top+plot_height}"/>',
        f'<text x="{left + plot_width/2}" y="{height-10}" '
        f'text-anchor="middle" font-size="14">Day</text>',
        f'<text x="18" y="{top + plot_height/2}" '
        f'text-anchor="middle" font-size="14" '
        f'transform="rotate(-90 18 {top + plot_height/2})">'
        'Commits</text>',
    ])

    # Line and circular points.
    coordinates = [
        (x_position(i), y_position(value))
        for i, value in enumerate(values)
    ]
    point_string = " ".join(
        f"{x:.2f},{y:.2f}" for x, y in coordinates
    )
    parts.append(f'<polyline class="line" points="{point_string}"/>')

    for index, (x, y) in enumerate(coordinates):
        value = values[index]
        parts.append(
            f'<circle class="point" cx="{x:.2f}" cy="{y:.2f}" r="5">'
            f'<title>{escape(labels[index])}: {value} commits</title>'
            '</circle>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def main():
    today = date.today()
    dates = [today - timedelta(days=i) for i in range(DAYS - 1, -1, -1)]

    labels = [day.strftime("%b %d") for day in dates]
    values = []

    for day in dates:
        count = get_daily_commits(day)
        values.append(count)
        print(f"{day.isoformat()}: {count} commits")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(make_svg(labels, values), encoding="utf-8")
    print(f"Graph saved to {OUTPUT}")


if __name__ == "__main__":
    main()
