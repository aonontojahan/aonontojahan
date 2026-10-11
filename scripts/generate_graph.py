
#!/usr/bin/env python3
"""
Generate an animated GitHub contribution graph with a green snake.

Snake direction:
    BODY / TAIL  -------------------->  HEAD
    LEFT                                  RIGHT

Output: assets/contribution-graph.svg
"""

from datetime import datetime, timedelta, timezone
from collections import Counter
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from xml.sax.saxutils import escape
import json
import os

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

USERNAME = "aonontojahan"
DAYS = 30

OUTPUT_FILE = Path("assets/contribution-graph.svg")

WIDTH = 1000
HEIGHT = 300

MARGIN_LEFT = 65
MARGIN_RIGHT = 30
MARGIN_TOP = 55
MARGIN_BOTTOM = 45

BACKGROUND = "#1F222E"
TITLE_COLOR = "#F85D7F"
ACCENT_COLOR = "#F8D866"
GRID_COLOR = "#343849"
TEXT_COLOR = "#E6E6E6"
LINE_COLOR = "#E8EAF0"

SNAKE_GREEN = "#39D353"
SNAKE_BORDER = "#167D2D"
TONGUE_COLOR = "#FF4D6D"

ANIMATION_DURATION = 8.0
SEGMENT_COUNT = 15
SEGMENT_DELAY = 0.075
HEAD_RADIUS = 9

# ---------------------------------------------------------
# Fetch recent public GitHub events
# ---------------------------------------------------------


def fetch_daily_commits(username: str, days: int) -> tuple[list, list]:
    """
    Fetch recent public GitHub events and count commits by date.

    Note: GitHub's public Events API is limited and may not include
    every contribution. Set GITHUB_TOKEN in the environment to improve
    API rate limits.
    """
    today = datetime.now(timezone.utc).date()
    dates = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]
    daily_counts = Counter()

    url = f"https://api.github.com/users/{username}/events?per_page=100"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{username}-contribution-graph",
    }

    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(url, headers=headers)

    try:
        with urlopen(request, timeout=20) as response:
            events = json.loads(response.read().decode("utf-8"))

        for event in events:
            event_date = datetime.fromisoformat(
                event["created_at"].replace("Z", "+00:00")
            ).date()

            if event_date not in dates:
                continue

            # PushEvent payloads contain commits from public repositories.
            if event.get("type") == "PushEvent":
                commits = event.get("payload", {}).get("commits", [])
                daily_counts[event_date] += len(commits)

    except (HTTPError, URLError, TimeoutError, ValueError, KeyError) as exc:
        print(f"Warning: Could not fetch GitHub events: {exc}")
        print("Generating the graph with zero counts for unavailable data.")

    counts = [daily_counts[d] for d in dates]
    return dates, counts


# ---------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------


def svg_text(x, y, text, size=10, color=TEXT_COLOR,
             anchor="middle", weight="normal"):
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" '
        f'font-family="Arial, Helvetica, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" '
        f'fill="{color}" text-anchor="{anchor}">'
        f'{escape(str(text))}</text>'
    )


def svg_circle(x, y, radius, fill, stroke="none", stroke_width=1):
    return (
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius:.2f}" '
        f'fill="{fill}" stroke="{stroke}" '
        f'stroke-width="{stroke_width}"/>'
    )


def make_path(points):
    """Create a smooth SVG path whose direction is left to right."""
    if not points:
        return ""

    if len(points) == 1:
        x, y = points[0]
        return f"M {x:.2f},{y:.2f} L {x + 0.01:.2f},{y:.2f}"

    # Catmull-Rom-style cubic Bézier interpolation.
    path = f"M {points[0][0]:.2f},{points[0][1]:.2f}"

    for i in range(len(points) - 1):
        x0, y0 = points[max(0, i - 1)]
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        x3, y3 = points[min(len(points) - 1, i + 2)]

        c1x = x1 + (x2 - x0) / 6
        c1y = y1 + (y2 - y0) / 6
        c2x = x2 - (x3 - x1) / 6
        c2y = y2 - (y3 - y1) / 6

        path += (
            f" C {c1x:.2f},{c1y:.2f}"
            f" {c2x:.2f},{c2y:.2f}"
            f" {x2:.2f},{y2:.2f}"
        )

    return path


# ---------------------------------------------------------
# Graph generation
# ---------------------------------------------------------


def generate_graph(dates, counts):
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    plot_width = WIDTH - MARGIN_LEFT - MARGIN_RIGHT
    plot_height = HEIGHT - MARGIN_TOP - MARGIN_BOTTOM

    max_count = max(max(counts, default=0), 5)
    y_max = max(5, ((max_count + 4) // 5) * 5)

    def x_position(index):
        if len(dates) <= 1:
            return MARGIN_LEFT + plot_width / 2
        return MARGIN_LEFT + index * plot_width / (len(dates) - 1)

    def y_position(value):
        return MARGIN_TOP + plot_height - (value / y_max) * plot_height

    points = [
        (x_position(i), y_position(count))
        for i, count in enumerate(counts)
    ]

    graph_path = make_path(points)
    parts = []

    # SVG header and background.
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}">'
    )
    parts.append(
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{BACKGROUND}"/>'
    )

    # Title.
    parts.append(
        svg_text(
            MARGIN_LEFT,
            28,
            "Daily GitHub Commit Progress",
            size=16,
            color=TITLE_COLOR,
            anchor="start",
            weight="bold",
        )
    )

    # Horizontal grid and Y-axis labels.
    tick_step = max(1, y_max // 5)
    ticks = list(range(0, y_max + 1, tick_step))
    if ticks[-1] != y_max:
        ticks.append(y_max)

    for tick in sorted(set(ticks)):
        y = y_position(tick)
        parts.append(
            f'<line x1="{MARGIN_LEFT}" y1="{y:.2f}" '
            f'x2="{WIDTH - MARGIN_RIGHT}" y2="{y:.2f}" '
            f'stroke="{GRID_COLOR}" stroke-width="1"/>'
        )
        parts.append(
            svg_text(
                MARGIN_LEFT - 12, y + 4, tick,
                size=10, color=TEXT_COLOR, anchor="end"
            )
        )

    # Vertical grid and date labels.
    label_indices = sorted(set(
        [0, len(dates) - 1]
        + list(range(0, len(dates), 3))
    ))

    for i in label_indices:
        x = x_position(i)
        parts.append(
            f'<line x1="{x:.2f}" y1="{MARGIN_TOP}" '
            f'x2="{x:.2f}" y2="{HEIGHT - MARGIN_BOTTOM}" '
            f'stroke="{GRID_COLOR}" stroke-width="1"/>'
        )

        label = dates[i].strftime("%b %d")
        parts.append(
            svg_text(
                x, HEIGHT - MARGIN_BOTTOM + 18,
                label, size=9, color=TEXT_COLOR
            )
        )

    # Axis labels.
    parts.append(
        f'<text x="18" y="{HEIGHT / 2:.2f}" '
        f'transform="rotate(-90 18 {HEIGHT / 2:.2f})" '
        f'font-family="Arial, Helvetica, sans-serif" '
        f'font-size="10" fill="{TEXT_COLOR}" text-anchor="middle">'
        f'Commits</text>'
    )

    # Commit line, drawn behind the snake.
    if graph_path:
        parts.append(
            f'<path d="{graph_path}" fill="none" '
            f'stroke="{LINE_COLOR}" stroke-width="2.2" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
        )

    # Commit markers.
    for i, (x, y) in enumerate(points):
        parts.append(
            svg_circle(
                x, y, 3.0, BACKGROUND,
                stroke=ACCENT_COLOR, stroke_width=1.5
            )
        )

    # Motion path is invisible and shared by every snake segment.
    # Its path direction follows the graph from left to right.
    parts.append(
        f'<path id="snake-motion-path" d="{graph_path}" '
        f'fill="none" stroke="none"/>'
    )

    # Draw the body first. The positive phase delay means that each
    # segment follows the head instead of moving ahead of it.
    #
    # begin = -(duration - delay) is equivalent to a positive delay
    # for a repeating animation, while keeping all segments visible
    # immediately when the SVG loads.
    for i in reversed(range(SEGMENT_COUNT)):
        delay = (SEGMENT_COUNT - i) * SEGMENT_DELAY
        begin_offset = -(ANIMATION_DURATION - delay)

        # Larger near the head, smaller toward the tail.
        radius = 2.7 + (SEGMENT_COUNT - i) * 0.34

        parts.append(
            f'<circle r="{radius:.2f}" '
            f'fill="{SNAKE_GREEN}" stroke="{SNAKE_BORDER}" '
            f'stroke-width="1.1">'
            f'<animateMotion dur="{ANIMATION_DURATION}s" '
            f'repeatCount="indefinite" '
            f'begin="{begin_offset:.3f}s" '
            f'rotate="auto" '
            f'path="{escape(graph_path, {chr(34): "&quot;"})}"/>'
            f'</circle>'
        )

    # Snake head: it has no phase delay, so it leads the body.
    # The eyes and tongue face forward in the direction of travel.
    head_begin = "0s"

    parts.append(
        f'<g>'
        f'<animateMotion dur="{ANIMATION_DURATION}s" '
        f'repeatCount="indefinite" begin="{head_begin}" '
        f'rotate="auto" '
        f'path="{escape(graph_path, {chr(34): "&quot;"})}"/>'

        # Head outline and face.
        f'<circle cx="0" cy="0" r="{HEAD_RADIUS}" '
        f'fill="{SNAKE_GREEN}" stroke="{SNAKE_BORDER}" '
        f'stroke-width="2"/>'

        # Eyes.
        f'<ellipse cx="3.0" cy="-3.1" rx="2.5" ry="3.0" '
        f'fill="#FFFFFF"/>'
        f'<ellipse cx="3.7" cy="-3.0" rx="1.1" ry="1.6" '
        f'fill="#17202A"/>'
        f'<ellipse cx="7.2" cy="-2.3" rx="2.3" ry="2.8" '
        f'fill="#FFFFFF"/>'
        f'<ellipse cx="7.8" cy="-2.2" rx="1.0" ry="1.5" '
        f'fill="#17202A"/>'

        # Tongue points forward, toward the right side of the graph.
        f'<path d="M 8,4 L 14,4 L 17,2 M 14,4 L 17,6" '
        f'fill="none" stroke="{TONGUE_COLOR}" '
        f'stroke-width="1.8" stroke-linecap="round" '
        f'stroke-linejoin="round"/>'

        f'</g>'
    )

    # Close SVG.
    parts.append("</svg>")

    OUTPUT_FILE.write_text("\n".join(parts), encoding="utf-8")
    print(f"Generated: {OUTPUT_FILE}")
    print(f"Dates: {len(dates)} | Commits counted: {sum(counts)}")


def main():
    dates, counts = fetch_daily_commits(USERNAME, DAYS)
    generate_graph(dates, counts)


if __name__ == "__main__":
    main()
