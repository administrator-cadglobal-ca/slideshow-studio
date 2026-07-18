"""Decoration themes registry - 3-level category tree."""

# Structure:
# CATEGORIES = {
#     category_id: {
#         name: str,
#         subcategories: {
#             subcategory_id: {
#                 name: str,
#                 themes: {
#                     theme_id: { name, description, clips: [...] }
#                 }
#             }
#         }
#     }
# }

CATEGORIES = {
    "occasions": {
        "name": "Occasions",
        "subcategories": {
            "wedding": {
                "name": "Wedding",
                "themes": {
                    "wedding-classic": {
                        "name": "Classic Wedding",
                        "description": "Hearts, roses, and gold sparkles",
                        "clips": [
                            {"file": "heart-gold.svg",   "positions": ["top-left", "top-right"],     "size": 10, "animate": "float-pulse",  "count": 2},
                            {"file": "rose-pink.svg",    "positions": ["bottom-left", "bottom-right"], "size": 12, "animate": "sway-gentle",  "count": 2},
                            {"file": "sparkle-gold.svg", "positions": ["center-top"],                "size": 8,  "animate": "twinkle",      "count": 1},
                        ],
                    },
                },
            },
            "party": {
                "name": "Party & Celebration",
                "themes": {
                    "party-fun": {
                        "name": "Fun Party",
                        "description": "Confetti, balloons, and stars",
                        "clips": [
                            {"file": "confetti.svg",   "positions": ["top-left", "top-right"],     "size": 15, "animate": "confetti-fall", "count": 2},
                            {"file": "balloon-red.svg","positions": ["bottom-right"],              "size": 12, "animate": "sway-gentle",  "count": 1},
                            {"file": "star-gold.svg",  "positions": ["top-left", "top-right", "bottom-left"], "size": 8,  "animate": "twinkle", "count": 3},
                        ],
                    },
                },
            },
            "nature": {
                "name": "Nature",
                "themes": {
                    "nature-butterflies": {
                        "name": "Butterflies & Flowers",
                        "description": "Butterflies dancing over pink flowers",
                        "clips": [
                            {"file": "butterfly.svg",   "positions": ["top-left", "top-right"],     "size": 12, "animate": "float-flutter", "count": 2},
                            {"file": "flower-pink.svg", "positions": ["bottom-left", "bottom-right"], "size": 10, "animate": "sway-gentle",  "count": 2},
                            {"file": "leaf-green.svg",  "positions": ["top-right"],                 "size": 10, "animate": "sway-gentle",  "count": 1},
                        ],
                    },
                },
            },
        },
    },
    "festivals": {
        "name": "Festivals",
        "subcategories": {
            "diwali": {
                "name": "Diwali",
                "themes": {
                    "diwali-classic": {
                        "name": "Diyas & Rangoli",
                        "description": "Traditional diyas with rangoli patterns",
                        "clips": [
                            {"file": "diya.svg",       "positions": ["bottom-left", "bottom-right"], "size": 10, "animate": "twinkle",     "count": 2},
                            {"file": "rangoli.svg",    "positions": ["top-left", "top-right"],       "size": 12, "animate": "sway-gentle","count": 2},
                            {"file": "firework.svg",   "positions": ["center-top"],                  "size": 15, "animate": "twinkle",     "count": 1},
                        ],
                    },
                },
            },
            "christmas": {
                "name": "Christmas",
                "themes": {
                    "christmas-classic": {
                        "name": "Trees & Stars",
                        "description": "Christmas trees, snowflakes, and stars",
                        "clips": [
                            {"file": "tree.svg",       "positions": ["bottom-left"], "size": 15, "animate": "sway-gentle","count": 1},
                            {"file": "snowflake.svg",  "positions": ["top-left", "top-right", "center-top"], "size": 8, "animate": "twinkle","count": 3},
                            {"file": "star-red.svg",   "positions": ["top-right"],                  "size": 10, "animate": "twinkle",     "count": 1},
                        ],
                    },
                },
            },
            "thanksgiving": {
                "name": "Thanksgiving",
                "themes": {
                    "thanksgiving-harvest": {
                        "name": "Autumn Harvest",
                        "description": "Autumn leaves and pumpkins",
                        "clips": [
                            {"file": "pumpkin.svg",     "positions": ["bottom-left", "bottom-right"], "size": 12, "animate": "sway-gentle","count": 2},
                            {"file": "autumn-leaf.svg", "positions": ["top-left", "top-right"],       "size": 10, "animate": "sway-gentle","count": 2},
                        ],
                    },
                },
            },
        },
    },
    "birthdays": {
        "name": "Birthdays",
        "subcategories": {
            "kids": {
                "name": "Kids",
                "themes": {
                    "kids-toys": {
                        "name": "Balloons & Toys",
                        "description": "Colorful balloons and toys for kids",
                        "clips": [
                            {"file": "balloon-multi.svg","positions": ["top-left", "top-right"], "size": 12, "animate": "sway-gentle","count": 2},
                            {"file": "cake.svg",         "positions": ["bottom-right"],           "size": 15, "animate": "float-pulse","count": 1},
                            {"file": "gift.svg",         "positions": ["bottom-left"],            "size": 12, "animate": "sway-gentle","count": 1},
                        ],
                    },
                },
            },
            "teen": {
                "name": "Teen",
                "themes": {
                    "teen-modern": {
                        "name": "Modern Vibes",
                        "description": "Neon stars and confetti",
                        "clips": [
                            {"file": "neon-star.svg",  "positions": ["top-left", "top-right", "bottom-left"], "size": 10, "animate": "twinkle","count": 3},
                            {"file": "confetti.svg",   "positions": ["center-top"],                "size": 15, "animate": "confetti-fall","count": 1},
                        ],
                    },
                },
            },
            "adults": {
                "name": "Adults",
                "themes": {
                    "adults-elegant": {
                        "name": "Elegant Celebration",
                        "description": "Gold sparkles and champagne",
                        "clips": [
                            {"file": "sparkle-gold.svg","positions": ["top-left", "top-right", "bottom-left", "bottom-right"], "size": 8, "animate": "twinkle","count": 4},
                            {"file": "champagne.svg",   "positions": ["bottom-right"],                          "size": 12,"animate": "sway-gentle","count": 1},
                        ],
                    },
                },
            },
        },
    },
}


def find_theme(theme_id):
    """Find a theme by its full theme_id across categories."""
    for cat in CATEGORIES.values():
        for sub in cat["subcategories"].values():
            if theme_id in sub["themes"]:
                theme = sub["themes"][theme_id].copy()
                # Attach category for clip lookup
                theme["_subcategory_id"] = None
                for sub_id, sub_data in cat["subcategories"].items():
                    if theme_id in sub_data["themes"]:
                        theme["_subcategory_id"] = sub_id
                return theme
    return None


def get_theme(theme_id):
    return find_theme(theme_id)


def list_categories():
    """Return the full category tree for the UI."""
    result = []
    for cat_id, cat in CATEGORIES.items():
        cat_out = {
            "id": cat_id,
            "name": cat["name"],
            "subcategories": [],
        }
        for sub_id, sub in cat["subcategories"].items():
            sub_out = {
                "id": sub_id,
                "name": sub["name"],
                "themes": [
                    {"id": tid, "name": t["name"], "description": t["description"]}
                    for tid, t in sub["themes"].items()
                ],
            }
            cat_out["subcategories"].append(sub_out)
        result.append(cat_out)
    return result


# Backwards compat: flat theme lookup
THEMES = {}
for _cat in CATEGORIES.values():
    for _sub in _cat["subcategories"].values():
        THEMES.update(_sub["themes"])


def list_themes():
    """Flat list (backwards compat)."""
    return [{"id": tid, "name": t["name"], "description": t["description"]}
            for tid, t in THEMES.items()]