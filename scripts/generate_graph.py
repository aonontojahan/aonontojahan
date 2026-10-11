
#!/usr/bin/env python3

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import json
import math
import os
import xml.sax.saxutils as saxutils

# =========================================================
# CONFIGURATION
# =========================================================

USERNAME = "aonontojahan"
DAYS = 30

OUTPUT_FILE = Path("assets/contribution-graph.svg")

WIDTH = 1000
HEIGHT = 300
LEFT = 65
RIGHT = 30
TOP = 55
BOTTOM = 45

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
SEGMENT_COUNT = 22
SEGMENT_DELAY = 0.055
HEAD_START_PROGRESS = 0.72


# =========================================================
# FETCH ACCOUNT-WIDE CONTRIBUTION DATA
# (matches GitHub's own green-squares counting)
# =========================================================

def fetch_contributions():
    """Fetch per-day *contribution* counts for the last 30 days.

    Uses contributionsCollection.contributionCalendar, which is the
    exact same source GitHub uses for the profile green-squares graph
    (commits, PRs, issues, reviews + private ones when the token
    allows). This is why earlier commit-only counting showed flat
    zeros for days that clearly have green squares.
    """
    token = os.getenv("PROFILE_TOKEN") or os.getenv("GITHUB_TOKEN")

    if not token:
        raise RuntimeError(
            "Missing token. Set PROFILE_TOKEN in your environment "
            "or GitHub Actions repository secrets."
        )

    today = datetime.now(timezone.utc).date()
    start_day = today - timedelta(days=DAYS - 1)

    # GraphQL accepts ISO-8601 timestamps.
    start_time = datetime.combine(
        start_day, datetime.min.time(), tzinfo=timezone.utc
    ).isoformat().replace("+00:00", "Z")

    end_time = datetime.combine(
        today + timedelta(days=1), datetime.min.time(),
        tzinfo=timezone.utc
    ).isoformat().replace("+00:00", "Z")

    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """

    payload = {
        "query": query,
        "variables": {
            "login": USERNAME,
            "from": start_time,
            "to": end_time,
        },
    }

    request = Request(
        "https://api.github.com/graphql",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "User-Agent": f"{USERNAME}-contribution-graph",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub GraphQL returned HTTP {exc.code}: {details}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(
            f"Could not connect to GitHub GraphQL: {exc}"
        ) from exc

    if result.get("errors"):
        raise RuntimeError(
            "GitHub GraphQL error: "
            + json.dumps(result["errors"], indent=2)
        )

    user = result.get("data", {}).get("user")
    if not user:
        raise RuntimeError(
            f"GitHub user '{USERNAME}' was not found or is inaccessible."
        )

    calendar = user["contributionsCollection"]["contributionCalendar"]

    counts_by_date = {}
    for week in calendar["weeks"]:
        for day_info in week["contributionDays"]:
            day = date.fromisoformat(day_info["date"])
            if start_day <= day <= today:
                counts_by_date[day] = day_info["contributionCount"]

    dates = [
        start_day + timedelta(days=i)
        for i in range(DAYS)
    ]
    counts = [counts_by_date.get(day, 0) for day in dates]

    print(f"GitHub account: {USERNAME}")
    print(f"Date range: {start_day} to {today}")
    print(f"Contributions in range: {sum(counts)}")
    print(f"GraphQL calendar total: {calendar['totalContributions']}")

    return dates, counts


# =========================================================
# SVG HELPERS
# =========================================================

def text_element(
    x, y, value, size=10, color=TEXT_COLOR,
    anchor="middle", weight="normal"
):
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" '
        f'font-family="Arial, Helvetica, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" '
        f'fill="{color}" text-anchor="{anchor}">'
        f'{saxutils.escape(str(value))}</text>'
    )


Y_TICKS = [0, 5, 10, 20, 30, 50, 80, 120, 150]
# Relative pixel share of each gap between consecutive ticks:
# first three gaps equal, then shrinking toward the top.
Y_GAP_WEIGHTS = [1.0, 1.0, 1.0, 0.8, 0.7, 0.6, 0.5, 0.4]


def nice_y_max(max_count):
    """Top of the Y axis: first fixed tick that fits the data."""
    for tick in Y_TICKS:
        if max_count <= tick:
            return tick
    # Beyond 150: keep stepping by 50.
    return int(math.ceil(max_count / 50) * 50)


def smooth_path(points, top, bottom, left, right):
    """Catmull-Rom spline clamped to the plot area.

    Without clamping, a flat 0 ... 0, 41 spike makes the spline
    overshoot below the x-axis (the dip seen before the last point).
    """
    if not points:
        return ""

    if len(points) == 1:
        x, y = points[0]
        return f"M {x:.2f},{y:.2f} L {x + 0.01:.2f},{y:.2f}"

    def clamp_x(v):
        return min(max(v, left), right)

    def clamp_y(v):
        return min(max(v, top), bottom)

    path = f"M {points[0][0]:.2f},{points[0][1]:.2f}"

    for i in range(len(points) - 1):
        x0, y0 = points[max(0, i - 1)]
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        x3, y3 = points[min(len(points) - 1, i + 2)]

        c1x = clamp_x(x1 + (x2 - x0) / 6)
        c1y = clamp_y(y1 + (y2 - y0) / 6)
        c2x = clamp_x(x2 - (x3 - x1) / 6)
        c2y = clamp_y(y2 - (y3 - y1) / 6)

        path += (
            f" C {c1x:.2f},{c1y:.2f}"
            f" {c2x:.2f},{c2y:.2f}"
            f" {x2:.2f},{y2:.2f}"
        )

    return path


# =========================================================
# ANIMATED SNAKE
# =========================================================

def add_snake(parts, graph_path):
    head_phase = ANIMATION_DURATION * HEAD_START_PROGRESS

    # The body tapers from the head toward a thin tail.
    for i in reversed(range(SEGMENT_COUNT)):
        delay = (i + 1) * SEGMENT_DELAY
        begin_offset = -(head_phase - delay)

        taper = 1.0 - (i / SEGMENT_COUNT)
        radius_x = 0.8 + 3.2 * (taper ** 0.75)
        radius_y = radius_x * 0.82

        parts.append(
            f'<ellipse rx="{radius_x:.2f}" ry="{radius_y:.2f}" '
            f'fill="{SNAKE_GREEN}" stroke="{SNAKE_BORDER}" '
            f'stroke-width="0.8">'
            f'<animateMotion dur="{ANIMATION_DURATION}s" '
            f'repeatCount="indefinite" '
            f'begin="{begin_offset:.3f}s" '
            f'rotate="auto" path="{graph_path}"/>'
            f'</ellipse>'
        )

    # Distinct head, eyes, and forked tongue.
    parts.append(
        '<g>'
        f'<animateMotion dur="{ANIMATION_DURATION}s" '
        f'repeatCount="indefinite" '
        f'begin="{-head_phase:.3f}s" '
        f'rotate="auto" path="{graph_path}"/>'

        f'<ellipse cx="0" cy="0" rx="7.5" ry="5.7" '
        f'fill="{SNAKE_GREEN}" stroke="{SNAKE_BORDER}" '
        f'stroke-width="1.5"/>'

        '<ellipse cx="2" cy="-2.3" rx="1.8" ry="1.9" fill="#FFFFFF"/>'
        '<circle cx="2.6" cy="-2.3" r="0.9" fill="#17202A"/>'
        '<ellipse cx="2" cy="2.3" rx="1.8" ry="1.9" fill="#FFFFFF"/>'
        '<circle cx="2.6" cy="2.3" r="0.9" fill="#17202A"/>'

        f'<path d="M 6,0 L 10,-1.8 M 6,0 L 10,1.8" '
        f'fill="none" stroke="{TONGUE_COLOR}" '
        f'stroke-width="1.4" stroke-linecap="round"/>'
        '</g>'
    )


# =========================================================
# BUILD GRAPH
# =========================================================

def generate_graph(dates, counts):
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    plot_width = WIDTH - LEFT - RIGHT
    plot_height = HEIGHT - TOP - BOTTOM

    max_count = max(counts, default=0)
    y_max = nice_y_max(max_count)

    def x_pos(index):
        return LEFT + index * plot_width / max(1, len(dates) - 1)

    # Custom scale ticks: 0, 5, 10, 20, 30, 50, 80, 120, 150.
    ticks = [t for t in Y_TICKS if t <= y_max]
    if ticks[-1] != y_max:
        ticks.append(y_max)

    # Custom piecewise scale: the gaps 0-5, 5-10, 10-20 are equal,
    # gaps shrink toward the top. Values between ticks interpolate
    # linearly inside their gap.
    weights = (
        Y_GAP_WEIGHTS[:len(ticks) - 1]
        + [0.3] * max(0, len(ticks) - 1 - len(Y_GAP_WEIGHTS))
    )
    bottom_y = HEIGHT - BOTTOM
    total_w = sum(weights)
    tick_y = {}
    cum = 0.0
    for i, tick in enumerate(ticks):
        if i > 0:
            cum += weights[i - 1]
        tick_y[tick] = bottom_y - (cum / total_w) * plot_height

    def y_pos(value):
        if value <= ticks[0]:
            return tick_y[ticks[0]]
        for j in range(len(ticks) - 1):
            if value <= ticks[j + 1]:
                frac = (value - ticks[j]) / (ticks[j + 1] - ticks[j])
                return (
                    tick_y[ticks[j]]
                    + frac * (tick_y[ticks[j + 1]] - tick_y[ticks[j]])
                )
        # Beyond the top tick: continue with the last gap's slope.
        slope = (
            (tick_y[ticks[-1]] - tick_y[ticks[-2]])
            / (ticks[-1] - ticks[-2])
        )
        return tick_y[ticks[-1]] + (value - ticks[-1]) * slope

    points = [
        (x_pos(i), y_pos(value))
        for i, value in enumerate(counts)
    ]
    graph_path = smooth_path(
        points, TOP, HEIGHT - BOTTOM, LEFT, WIDTH - RIGHT
    )

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}">',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{BACKGROUND}"/>',
        text_element(
            LEFT, 28, "Daily GitHub Commit Progress",
            size=16, color=TITLE_COLOR,
            anchor="start", weight="bold"
        ),
    ]

    # Horizontal grid and labels on the fixed custom scale.
    for tick in sorted(set(ticks)):
        y = y_pos(tick)
        parts.append(
            f'<line x1="{LEFT}" y1="{y:.2f}" '
            f'x2="{WIDTH - RIGHT}" y2="{y:.2f}" '
            f'stroke="{GRID_COLOR}" stroke-width="1"/>'
        )
        parts.append(
            text_element(LEFT - 12, y + 4, tick, anchor="end")
        )

    # Vertical grid and date labels.
    label_indices = sorted(
        set([0, len(dates) - 1] + list(range(0, len(dates), 3)))
    )

    for i in label_indices:
        x = x_pos(i)
        parts.append(
            f'<line x1="{x:.2f}" y1="{TOP}" '
            f'x2="{x:.2f}" y2="{HEIGHT - BOTTOM}" '
            f'stroke="{GRID_COLOR}" stroke-width="1"/>'
        )
        parts.append(
            text_element(
                x, HEIGHT - BOTTOM + 18,
                dates[i].strftime("%b %d"), size=9
            )
        )

    parts.append(
        f'<text x="18" y="{HEIGHT / 2:.2f}" '
        f'transform="rotate(-90 18 {HEIGHT / 2:.2f})" '
        f'font-family="Arial, Helvetica, sans-serif" '
        f'font-size="10" fill="{TEXT_COLOR}" '
        f'text-anchor="middle">Commits</text>'
    )

    # Graph line and daily markers.
    parts.append(
        f'<path d="{graph_path}" fill="none" '
        f'stroke="{LINE_COLOR}" stroke-width="2.2" '
        f'stroke-linejoin="round" stroke-linecap="round"/>'
    )

    for (x, y), day, value in zip(points, dates, counts):
        parts.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.8" '
            f'fill="{BACKGROUND}" stroke="{ACCENT_COLOR}" '
            f'stroke-width="1.4">'
            f'<title>{day.strftime("%b %d")}: {value} commits</title>'
            f'</circle>'
        )

    add_snake(parts, graph_path)
    parts.append("</svg>")

    OUTPUT_FILE.write_text("\n".join(parts), encoding="utf-8")

    print(f"Generated: {OUTPUT_FILE}")
    print(f"Days plotted: {len(dates)}")


def main():
    dates, counts = fetch_contributions()
    generate_graph(dates, counts)


if __name__ == "__main__":
    main()
