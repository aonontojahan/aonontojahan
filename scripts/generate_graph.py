
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

WIDTH = 1100
HEIGHT = 240

LEFT, RIGHT, TOP, BOTTOM = 65, 25, 38, 55
PLOT_WIDTH = WIDTH - LEFT - RIGHT
PLOT_HEIGHT = HEIGHT - TOP - BOTTOM

# Tokyo Night colors
BG = "#1F222E"
GRID = "#343849"
WHITE = "#FFFFFF"
PINK = "#F85D7F"
YELLOW = "#F8D866"
GREEN = "#39D353"
GREEN_DARK = "#167D2D"
TONGUE = "#FF4D6D"


def get_daily_commits(day):
    """Get the daily commit count from GitHub's commit-search API."""
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
            result = json.load(response)
            return int(result.get("total_count", 0))
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub API error on {day}: HTTP {error.code}: {details}"
        ) from error


def make_svg(labels, values):
    maximum = max(values, default=0)
    y_max = max(5, ((maximum + 4) // 5) * 5)

    def x_pos(index):
        if len(values) <= 1:
            return LEFT + PLOT_WIDTH / 2
        return LEFT + index * PLOT_WIDTH / (len(values) - 1)

    def y_pos(value):
        return TOP + PLOT_HEIGHT - (value / y_max) * PLOT_HEIGHT

    coordinates = [
        (x_pos(i), y_pos(value))
        for i, value in enumerate(values)
    ]

    path_data = " ".join(
        ("M" if i == 0 else "L") + f" {x:.2f} {y:.2f}"
        for i, (x, y) in enumerate(coordinates)
    )
    safe_path = escape(path_data, {'"': "&quot;"})

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" '
        'role="img" aria-labelledby="title desc">',

        '<title id="title">Daily GitHub Commit Progress</title>',
        f'<desc id="desc">Daily commit counts for {escape(USERNAME)} '
        f'over the last {DAYS} days.</desc>',

        f'<rect width="100%" height="100%" fill="{BG}"/>',

        '<style>',
        'text{font-family:Arial,Helvetica,sans-serif;fill:#FFFFFF}',
        f'.grid{{stroke:{GRID};stroke-width:1}}',
        '.axis{stroke:#697386;stroke-width:1.5}',
        f'.commit-line{{fill:none;stroke:{WHITE};stroke-width:3;'
        'stroke-linejoin:round;stroke-linecap:round}',
        f'.commit-point{{fill:{BG};stroke:{YELLOW};stroke-width:2}}',
        f'.chart-title{{fill:{PINK}}}',
        '</style>',

        '<text class="chart-title" x="65" y="22" '
        'font-size="16" font-weight="600">'
        'Daily GitHub Commit Progress</text>',
    ]

    # Y-axis
    step = max(1, y_max // 4)
    ticks = list(range(0, y_max + 1, step))
    if ticks[-1] != y_max:
        ticks.append(y_max)

    for tick in ticks:
        y = y_pos(tick)
        parts.append(
            f'<line class="grid" x1="{LEFT}" y1="{y:.2f}" '
            f'x2="{WIDTH-RIGHT}" y2="{y:.2f}"/>'
        )
        parts.append(
            f'<text x="{LEFT-12}" y="{y+4:.2f}" '
            f'text-anchor="end" font-size="11">{tick}</text>'
        )

    # X-axis
    for i, label in enumerate(labels):
        if i % 3 == 0 or i == len(labels) - 1:
            x = x_pos(i)
            parts.append(
                f'<line class="grid" x1="{x:.2f}" y1="{TOP}" '
                f'x2="{x:.2f}" y2="{TOP+PLOT_HEIGHT}"/>'
            )
            parts.append(
                f'<text x="{x:.2f}" y="{TOP+PLOT_HEIGHT+18}" '
                f'text-anchor="middle" font-size="10">'
                f'{escape(label)}</text>'
            )

    parts.extend([
        f'<line class="axis" x1="{LEFT}" y1="{TOP}" '
        f'x2="{LEFT}" y2="{TOP+PLOT_HEIGHT}"/>',
        f'<line class="axis" x1="{LEFT}" y1="{TOP+PLOT_HEIGHT}" '
        f'x2="{WIDTH-RIGHT}" y2="{TOP+PLOT_HEIGHT}"/>',
        f'<text x="15" y="{TOP+PLOT_HEIGHT/2}" '
        f'text-anchor="middle" font-size="11" '
        f'transform="rotate(-90 15 {TOP+PLOT_HEIGHT/2})">'
        'Commits</text>',
    ])

    # Draw the commit line
    point_string = " ".join(
        f"{x:.2f},{y:.2f}" for x, y in coordinates
    )
    parts.append(
        f'<polyline id="commit-path" class="commit-line" '
        f'points="{point_string}"/>'
    )

    # Commit points
    for i, (x, y) in enumerate(coordinates):
        parts.append(
            f'<circle class="commit-point" cx="{x:.2f}" '
            f'cy="{y:.2f}" r="3">'
            f'<title>{escape(labels[i])}: {values[i]} commits</title>'
            '</circle>'
        )

    # Animated snake.
    # The body uses the same path and duration as the head.
    # Positive begin offsets make body segments start after the head.
    if len(coordinates) >= 2:
        segment_count = 12
        duration = 8

        for i in range(segment_count, 0, -1):
            delay = i * 0.075
            radius_x = max(3.5, 7.0 - i * 0.28)
            radius_y = max(3.0, 5.5 - i * 0.20)

            parts.append(
                f'<ellipse cx="0" cy="0" '
                f'rx="{radius_x:.2f}" ry="{radius_y:.2f}" '
                f'fill="{GREEN}" stroke="{GREEN_DARK}" '
                'stroke-width="1.2">'
                f'<animateMotion dur="{duration}s" '
                'repeatCount="indefinite" '
                f'begin="{delay:.3f}s" rotate="auto" '
                f'path="{safe_path}"/>'
                '</ellipse>'
            )

        # Head: begins immediately and leads the body.
        parts.extend([
            '<g>',
            f'<ellipse cx="0" cy="0" rx="10" ry="8" '
            f'fill="{GREEN}" stroke="{GREEN_DARK}" stroke-width="2"/>',

            # Eyes
            '<ellipse cx="-3.5" cy="-3" rx="2.4" ry="2.8" '
            'fill="#FFFFFF"/>',
            '<ellipse cx="4" cy="-3" rx="2.4" ry="2.8" '
            'fill="#FFFFFF"/>',
            '<circle cx="-3" cy="-2.5" r="1.3" fill="#111111"/>',
            '<circle cx="4.5" cy="-2.5" r="1.3" fill="#111111"/>',

            # Nostril
            '<circle cx="7" cy="1" r="0.8" fill="#145523"/>',

            # Forked tongue
            f'<path d="M 1,6 L 1,11 L -2,14 M 1,11 L 4,14" '
            f'fill="none" stroke="{TONGUE}" stroke-width="1.8" '
            'stroke-linecap="round" stroke-linejoin="round"/>',

            f'<animateMotion dur="{duration}s" '
            'repeatCount="indefinite" rotate="auto" '
            f'path="{safe_path}"/>',
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
