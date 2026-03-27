ROUND_MAKER_TEMPLATE_OPTIONS = [
    {
        "value": "theme1",
        "label": "Minimal",
        "presentation_id": "109EgKCocHzTtUF9hVJVKEfV0HzFjaBfpWPKXaLNsos0",
        "supports_icons": False,
        "requires_round_analysis": False,
        "smart_category_routing": False,
    },
    {
        "value": "theme3",
        "label": "Plain",
        "presentation_id": "1ZFahoyu0FSUx84IldZjcfTVMKTOzfRevArv9K3KPkmw",
        "supports_icons": False,
        "requires_round_analysis": False,
        "smart_category_routing": False,
    },
    {
        "value": "theme2",
        "label": "Trivial Pursuit",
        "presentation_id": "1x8J9cEpFeMMYAJ_Inxw4Z_2-zYBwa5NMfOsN8pZKVHQ",
        "supports_icons": True,
        "requires_round_analysis": False,
        "smart_category_routing": False,
    },
    {
        "value": "theme4",
        "label": "Geography",
        "presentation_id": "1w0F26wa0aPGjwJMr33SUXB99C41lZVxF5oMYbhpTL6M",
        "supports_icons": False,
        "requires_round_analysis": False,
        "smart_category_routing": False,
    },
    {
        "value": "theme5",
        "label": "Trivial Pursuit (Smart)",
        "presentation_id": "1E0eNh79SX2ZNf-264wQERxPKFhgf2e2BAyrpSEJtyMw",
        "supports_icons": False,
        "requires_round_analysis": True,
        "smart_category_routing": True,
    },
]

ROUND_MAKER_TEMPLATE_BY_VALUE = {
    option["value"]: option
    for option in ROUND_MAKER_TEMPLATE_OPTIONS
}

ROUND_MAKER_TEMPLATE_BY_PRESENTATION_ID = {
    option["presentation_id"]: option
    for option in ROUND_MAKER_TEMPLATE_OPTIONS
}

SMART_TRIVIAL_PURSUIT_TEMPLATE_ID = ROUND_MAKER_TEMPLATE_BY_VALUE["theme5"]["presentation_id"]
SMART_TRIVIAL_PURSUIT_CATEGORIES = [
    "GEOGRAPHY",
    "FOOD",
    "FILM",
    "SCIENCE",
    "NATURE",
    "LAW",
    "ANIMALS",
    "PHILOSOPHY",
    "CURRENTEVENTS",
    "HISTORY",
    "GAMES",
    "THEATER",
    "ARTS",
    "LITERATURE",
    "SPORTS",
    "FOOTBALL",
    "TECHNOLOGY",
    "WRITING",
    "ENTERTAINMENT",
]
