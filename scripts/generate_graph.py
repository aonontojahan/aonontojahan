
#!/usr/bin/env python3

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import subprocess
import xml.sax.saxutils as saxutils


# =========================================================
# CONFIGURATION
# =========================================================

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

# Head starts around the right side of the graph.
HEAD_START_PROGRESS = 0.72


# =========================================================
# READ REAL COMMITS FROM GIT
# =========================================================

def get_daily_commits():
    """
    Count commits in this repository by commit date.

    Run this script from the repository root.
    Includes commits present in the checked-out Git history.
    """

    today = datetime.now(timezone.utc).date()
    dates = [
        today - timedelta(days=i)
        for i in range(DAYS - 1, -1, -1)
    ]

    counts = Counter()

    since_date = dates[0].isoformat()

    try:
        result = subprocess.run(
            [
                "git",
                "log",
                "--all",
                "--since",
                f"{since_date} 00:00:00",
                "--date=short",
                "--format=%ad",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )

        for line in result.stdout.splitlines():
            line = line.strip()

            if not line:
                continue

            try:
                commit_date = date.fromisoformat(line)
            except ValueError:
                continue

            if dates[0] <= commit_date <= dates[-1]:
                counts[commit_date] += 1

    except FileNotFoundError:
        raise RuntimeError(
            "Git was not found. Install Git and run this script "
            "from inside your repository."
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Could not read Git history: {exc.stderr}"
        ) from exc

    daily_counts = [counts[d] for d in dates]

    print(f"Repository: {Path.cwd()}")
    print(f"Date range: {dates[0]} to {dates[-1]}")
    print(f"Commits counted: {sum(daily_counts)}")

    if not sum(daily_counts):
        print(
            "Warning: No commits found in this repository "
            "for this date range. Check git log and the dates."
        )

    return dates, daily_counts


# =========================================================
# SVG HELPERS
# =========================================================

def text_element(
    x, y, value, size=10, color=TEXT_COLOR,
    anchor="middle", weight="normal"
):
    value = saxutils.escape(str(value))
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" '
        f'font-family="Arial, Helvetica, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" '
        f'fill="{color}" text-anchor="{anchor}">'
        f'{value}</text>'
    )


def smooth_path(points):
    if len(points) < 2:
        if not points:
            return ""
        x, y = points[0]
        return f"M {x:.2f},{y:.2f} L {x + 0.01:.2f},{y:.2f}"

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


# =========================================================
# SNAKE ANIMATION
# =========================================================

def add_snake(parts, path):
    head_phase = ANIMATION_DURATION * HEAD_START_PROGRESS

    # Draw the tail first, then the body, so the head appears
    # visually in front of the trailing segments.
    for i in reversed(range(SEGMENT_COUNT)):
        delay = (i + 1) * SEGMENT_DELAY
        begin_offset = -(head_phase - delay)

        # i=0 is closest to the head; larger i means tailward.
        taper = 1.0 - (i / SEGMENT_COUNT)

        # Radius shrinks toward the tail.
        rx = 0.8 + 3.2 * (taper ** 0.75)
        ry = rx * 0.82

        parts.append(
            f'<ellipse rx="{rx:.2f}" ry="{ry:.2f}" '
            f'fill="{SNAKE_GREEN}" '
            f'stroke="{SNAKE_BORDER}" stroke-width="0.8">'
            f'<animateMotion dur="{ANIMATION_DURATION}s" '
            f'repeatCount="indefinite" '
            f'begin="{begin_offset:.3f}s" '
            f'rotate="auto" path="{path}"/>'
            f'</ellipse>'
        )

    # Head: larger and clearly distinguishable from the body.
    parts.append(
        '<g>'
        f'<animateMotion dur="{ANIMATION_DURATION}s" '
        f'repeatCount="indefinite" '
        f'begin="{-head_phase:.3f}s" '
        f'rotate="auto" path="{path}"/>'

        '<ellipse cx="0" cy="0" rx="7.5" ry="5.7" '
        f'fill="{SNAKE_GREEN}" stroke="{SNAKE_BORDER}" '
        'stroke-width="1.5"/>'

        # Eyes
        '<ellipse cx="2" cy="-2.3" rx="1.8" ry="1.9" '
        'fill="#FFFFFF"/>'
        '<circle cx="2.6" cy="-2.3" r="0.9" fill="#17202A"/>'

        '<ellipse cx="2" cy="2.3" rx="1.8" ry="1.9" '
        'fill="#FFFFFF"/>'
        '<circle cx="2.6" cy="2.3" r="0.9" fill="#17202A"/>'

        # Mouth and forked tongue
        f'<path d="M 4,0 L 6.5,0" stroke="{SNAKE_BORDER}" '
        'stroke-width="0.9" fill="none"/>'
        f'<path d="M 6,0 L 10,-1.8 M 6,0 L 10,1.8" '
        f'stroke="{TONGUE_COLOR}" stroke-width="1.4" '
        'stroke-linecap="round" fill="none"/>'
        '</g>'
    )


# =========================================================
# GRAPH GENERATION
# =========================================================

def generate_graph(dates, counts):
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    plot_width = WIDTH - LEFT - RIGHT
    plot_height = HEIGHT - TOP - BOTTOM

    max_count = max(counts, default=0)
    y_max = max(5, ((max_count + 4) // 5) * 5)

    def x_pos(i):
        return LEFT + i * plot_width / max(1, len(dates) - 1)

    def y_pos(value):
        return TOP + plot_height - (value / y_max) * plot_height

    points = [
        (x_pos(i), y_pos(value))
        for i, value in enumerate(counts)
    ]

    path = smooth_path(points)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}">',
        f'<rect width="{WIDTH}" height="{HEIGHT}" '
        f'fill="{BACKGROUND}"/>',
        text_element(
            LEFT, 28, "Daily GitHub Commit Progress",
            size=16, color=TITLE_COLOR,
            anchor="start", weight="bold"
        ),
    ]

    # Horizontal grid and scale labels.
    tick_step = max(1, y_max // 5)
    ticks = list(range(0, y_max + 1, tick_step))
    if ticks[-1] != y_max:
        ticks.append(y_max)

    for tick in sorted(set(ticks)):
        y = y_pos(tick)

        parts.append(
            f'<line x1="{LEFT}" y1="{y:.2f}" '
            f'x2="{WIDTH - RIGHT}" y2="{y:.2f}" '
            f'stroke="{GRID_COLOR}" stroke-width="1"/>'
        )
        parts.append(
            text_element(
                LEFT - 12, y + 4, tick,
                size=10, anchor="end"
            )
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

    # Actual daily commit line.
    parts.append(
        f'<path d="{path}" fill="none" '
        f'stroke="{LINE_COLOR}" stroke-width="2.2" '
        f'stroke-linejoin="round" stroke-linecap="round"/>'
    )

    # Daily markers.
    for x, y in points:
        parts.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.8" '
            f'fill="{BACKGROUND}" stroke="{ACCENT_COLOR}" '
            f'stroke-width="1.4"/>'
        )

    # Animated snake follows the graph path.
    add_snake(parts, path)

    parts.append("</svg>")

    OUTPUT_FILE.write_text("\n".join(parts), encoding="utf-8")

    print(f"Generated: {OUTPUT_FILE}")
    print(f"Days: {len(dates)}")


def main():
    dates, counts = get_daily_commits()
    generate_graph(dates, counts)


if __name__ == "__main__":
    main()
