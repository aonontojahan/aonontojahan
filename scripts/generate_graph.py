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

DAYS = 30
OUTPUT = Path("assets/contribution-graph.svg")

# SVG dimensions: compact chart, 2.5-inch target display height.
WIDTH = 1100
HEIGHT = 240

LEFT = 65
RIGHT = 25
TOP = 38
BOTTOM = 55

PLOT_WIDTH = WIDTH - LEFT - RIGHT
PLOT_HEIGHT = HEIGHT - TOP - BOTTOM


def get_daily_commits(day):
    """Retrieve the number of commits authored by the user on a date."""
    query = f"author:{USERNAME} author-date:{day.isoformat()}"
    url = "https://api.github.com/search/commits?" + urllib.parse.urlencode(
        {"q": query, "per_page": 1}
    )

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
            f"GitHub API returned HTTP {error.code} for {day}: {details}"
        ) from error


def make_svg(labels, values):
    maximum = max(values, default=0)
    y_max = max(5, ((maximum + 4) // 5) * 5)

    def x_position(index):
        if len(values) <= 1:
            return LEFT + PLOT_WIDTH / 2
        return LEFT + index * PLOT_WIDTH / (len(values) - 1)

    def y_position(value):
        return TOP + PLOT_HEIGHT - (value / y_max) * PLOT_HEIGHT

    coordinates = [
        (x_position(i), y_position(value))
        for i, value in enumerate(values)
    ]

    path_data = " ".join(
        ("M" if i == 0 else "L") + f" {x:.2f} {y:.2f}"
        for i, (x, y) in enumerate(coordinates)
    )

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" '
        'role="img" aria-labelledby="title desc">',
        '<title id="title">Daily GitHub Commit Progress</title>',
        f'<desc id="desc">Daily commit counts for {escape(USERNAME)} '
        f'over the last {DAYS} days.</desc>',

        # Black background and compact typography.
        '<rect width="100%" height="100%" fill="#000000"/>',
        '<style>',
        'text{font-family:Arial,Helvetica,sans-serif;fill:#FFFFFF}',
        '.grid{stroke:#303030;stroke-width:1}',
        '.axis{stroke:#777777;stroke-width:1.5}',
        '.commit-line{fill:none;stroke:#FFFFFF;stroke-width:3;'
        'stroke-linejoin:round;stroke-linecap:round}',
        '.commit-point{fill:#000000;stroke:#FFFFFF;stroke-width:2}',
        '</style>',

        '<text x="65" y="22" font-size="16" font-weight="600">'
        'Daily GitHub Commit Progress</text>',
    ]

    # Horizontal gridlines and commit-count labels.
    tick_step = max(1, y_max // 4)
    ticks = list(range(0, y_max + 1, tick_step))
    if ticks[-1] != y_max:
        ticks.append(y_max)

    for tick in ticks:
        y = y_position(tick)
        parts.append(
            f'<line class="grid" x1="{LEFT}" y1="{y:.2f}" '
            f'x2="{WIDTH - RIGHT}" y2="{y:.2f}"/>'
        )
        parts.append(
            f'<text x="{LEFT - 12}" y="{y + 4:.2f}" '
            f'text-anchor="end" font-size="11">{tick}</text>'
        )

    # Vertical gridlines and readable date labels.
    for index, label in enumerate(labels):
        if index % 3 == 0 or index == len(labels) - 1:
            x = x_position(index)
            parts.append(
                f'<line class="grid" x1="{x:.2f}" y1="{TOP}" '
                f'x2="{x:.2f}" y2="{TOP + PLOT_HEIGHT}"/>'
            )
            parts.append(
                f'<text x="{x:.2f}" y="{TOP + PLOT_HEIGHT + 18}" '
                f'text-anchor="middle" font-size="10">'
                f'{escape(label)}</text>'
            )

    # Axes.
    parts.extend([
        f'<line class="axis" x1="{LEFT}" y1="{TOP}" '
        f'x2="{LEFT}" y2="{TOP + PLOT_HEIGHT}"/>',
        f'<line class="axis" x1="{LEFT}" y1="{TOP + PLOT_HEIGHT}" '
        f'x2="{WIDTH - RIGHT}" y2="{TOP + PLOT_HEIGHT}"/>',
        f'<text x="15" y="{TOP + PLOT_HEIGHT / 2}" '
        f'text-anchor="middle" font-size="11" '
        f'transform="rotate(-90 15 {TOP + PLOT_HEIGHT / 2})">'
        'Commits</text>',
    ])

    # Actual daily commit line.
    parts.append(
        f'<polyline id="commit-path" class="commit-line" '
        f'points="{" ".join(f"{x:.2f},{y:.2f}" for x, y in coordinates)}"/>'
    )

    # Static points for every day.
    for index, (x, y) in enumerate(coordinates):
        parts.append(
            f'<circle class="commit-point" cx="{x:.2f}" cy="{y:.2f}" '
            f'r="3"><title>{escape(labels[index])}: '
            f'{values[index]} commits</title></circle>'
        )

    # Animated snake following the plotted commit line.
    # Animation support depends on the SVG viewer; GitHub README
    # images may not play this animation.
    if coordinates:
        animation_path = escape(path_data, {'"': '&quot;'})

        # Body segments follow the same path with staggered start offsets.
        for index, offset in enumerate((0, 0.18, 0.36, 0.54, 0.72)):
            radius = 5.5 - index * 0.5
            parts.append(
                f'<circle r="{radius:.1f}" fill="#FFFFFF" '
                'stroke="#000000" stroke-width="1.5">'
                f'<animateMotion dur="8s" repeatCount="indefinite" '
                f'begin="-{offset}s" path="{animation_path}"/>'
                '</circle>'
            )

        # Snake head, with black eyes, follows the same line.
        parts.extend([
            '<g>',
            '<circle r="7" fill="#FFFFFF" stroke="#000000" '
            'stroke-width="1.5"/>',
            '<circle cx="-2.5" cy="-2" r="1.2" fill="#000000"/>',
            '<circle cx="2.5" cy="-2" r="1.2" fill="#000000"/>',
            f'<animateMotion dur="8s" repeatCount="indefinite" '
            f'path="{animation_path}"/>',
            '</g>',
        ])

    parts.append("</svg>")
    return "\n".join(parts)


def main():
    if not TOKEN:
        raise RuntimeError("GITHUB_TOKEN is missing.")

    today = date.today()
    dates = [
        today - timedelta(days=i)
        for i in range(DAYS - 1, -1, -1)
    ]

    labels = [day.strftime("%b %d") for day in dates]
    values = []

    for day in dates:
        count = get_daily_commits(day)
        values.append(count)
        print(f"{day.isoformat()}: {count} commits")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(make_svg(labels, values), encoding="utf-8")
    print(f"Generated graph: {OUTPUT}")


if __name__ == "__main__":
    main()