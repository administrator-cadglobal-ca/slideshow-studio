"""Decoration themes registry - defines available themes and their clips."""

# Each theme has:
# - name: display name
# - description: short description
# - clips: list of clip objects each with:
#   - file: relative path in /app/static/clips/<theme>/<file>
#   - positions: list of allowed positions (top-left, top-right, bottom-left, bottom-right, center)
#   - size: percentage of frame width (e.g. 15 = 15%)
#   - animate: CSS animation class or None
#   - count: how many to show per photo (randomly chosen from positions)

THEMES = {
    "wedding": {
        "name": "Wedding",
        "description": "Elegant hearts, rings, and floral accents",
        "clips": [
            {"file": "heart-gold.svg",   "positions": ["top-left", "top-right"],     "size": 10, "animate": "float-pulse",  "count": 2},
            {"file": "rose-pink.svg",    "positions": ["bottom-left", "bottom-right"], "size": 12, "animate": "sway-gentle",  "count": 2},
            {"file": "sparkle-gold.svg", "positions": ["center-top"],                "size": 8,  "animate": "twinkle",      "count": 1},
        ],
    },
    "party": {
        "name": "Party & Celebration",
        "description": "Festive confetti, balloons, and sparkles",
        "clips": [
            {"file": "confetti.svg",   "positions": ["top-left", "top-right"],     "size": 15, "animate": "confetti-fall", "count": 2},
            {"file": "balloon-red.svg","positions": ["bottom-right"],              "size": 12, "animate": "sway-gentle",  "count": 1},
            {"file": "star-gold.svg",  "positions": ["top-left", "top-right", "bottom-left"], "size": 8,  "animate": "twinkle", "count": 3},
        ],
    },
    "nature": {
        "name": "Nature & Flowers",
        "description": "Butterflies, leaves, and blooming flowers",
        "clips": [
            {"file": "butterfly.svg",   "positions": ["top-left", "top-right"],     "size": 12, "animate": "float-flutter", "count": 2},
            {"file": "flower-pink.svg", "positions": ["bottom-left", "bottom-right"], "size": 10, "animate": "sway-gentle",  "count": 2},
            {"file": "leaf-green.svg",  "positions": ["top-right"],                 "size": 10, "animate": "sway-gentle",  "count": 1},
        ],
    },
}


def get_theme(theme_id):
    return THEMES.get(theme_id)


def list_themes():
    return [
        {"id": tid, "name": t["name"], "description": t["description"]}
        for tid, t in THEMES.items()
    ]