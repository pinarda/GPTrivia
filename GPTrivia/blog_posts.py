from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BlogPostEntry:
    url_name: str
    title: str
    display_date: str
    category: str
    summary: str


ROBOALEX_COVARIANCE_COLUMNS = [
    "Zach",
    "Megan",
    "Ichigo",
    "Jenny",
    "Mom",
    "Dad",
    "Chris",
    "Alex",
    "Jeff",
    "Drew",
]


@dataclass(frozen=True)
class CovarianceRow:
    label: str
    values: tuple[float, ...]


ROBOALEX_COVARIANCE_ROWS = (
    CovarianceRow("Drew", (0.174454059943789, 0.130736981467213, 0.168260077403877, 0.0584321042656785, 0.383516413854523, 0.257796342597267, 0.33184598452371, 0.249237664155715, 0.219735148797198, 0.965313779158965)),
    CovarianceRow("Jeff", (0.0, 0.102446065576477, 0.0529395668926205, 0.0423049889873948, 0.0424570809701508, 0.33164351589859, 0.0484174079767664, 0.238945611734372, 0.644472777141622, 0.219735148797198)),
    CovarianceRow("Alex", (0.275496731668697, 0.391369075010627, 0.456734694112276, 0.219152358425186, 0.148305267060515, 0.57243192268961, 0.441072089766981, 0.931622952564687, 0.238945611734372, 0.249237664155715)),
    CovarianceRow("Chris", (0.235718175220323, 0.273961971836896, 0.232855603690639, 0.147792511473566, 0.244597362288759, 0.269977145643064, 0.979869849965593, 0.441072089766981, 0.0484174079767664, 0.33184598452371)),
    CovarianceRow("Dad", (0.292861342836609, 0.363155947166633, 0.206093127359858, 0.269596711205491, 0.193496439846076, 0.96442732970944, 0.269977145643064, 0.57243192268961, 0.33164351589859, 0.257796342597267)),
    CovarianceRow("Mom", (0.158246411714412, 0.452554560084777, 0.213486484738421, 0.37811162283317, 0.983503198369208, 0.193496439846076, 0.244597362288759, 0.148305267060515, 0.0424570809701508, 0.383516413854523)),
    CovarianceRow("Jenny", (0.341114532630189, 0.548738120869712, 0.192061110045578, 1.0, 0.37811162283317, 0.269596711205491, 0.147792511473566, 0.219152358425186, 0.0423049889873948, 0.0584321042656785)),
    CovarianceRow("Ichigo", (0.17442773970944, 0.325966026924173, 0.879542061404271, 0.192061110045578, 0.213486484738421, 0.206093127359858, 0.232855603690639, 0.456734694112276, 0.0529395668926205, 0.168260077403877)),
    CovarianceRow("Megan", (0.435882588419654, 0.991041150827902, 0.325966026924173, 0.548738120869712, 0.452554560084777, 0.363155947166633, 0.273961971836896, 0.391369075010627, 0.102446065576477, 0.130736981467213)),
    CovarianceRow("Zach", (0.602211486228072, 0.435882588419654, 0.17442773970944, 0.341114532630189, 0.158246411714412, 0.292861342836609, 0.235718175220323, 0.275496731668697, 0.0, 0.174454059943789)),
)


BLOG_POSTS = (
    BlogPostEntry(
        url_name="blog_roboalex",
        title="roboAlex 1.0",
        display_date="May 17, 2021",
        category="Trivia Stats / Modeling",
        summary="A preserved write-up from the original trivia-stats blog about modeling one player's scores with simple statistical assumptions.",
    ),
    BlogPostEntry(
        url_name="blog_joker_stats",
        title="Joker Stats",
        display_date="September 9, 2020",
        category="Trivia Stats / Jokers",
        summary="An archived joker strategy post covering creator bias, judgement tables, and the original distribution plots by creator.",
    ),
    BlogPostEntry(
        url_name="blog_other_trivia_plots",
        title="Other Trivia Plots",
        display_date="August 18, 2020",
        category="Trivia Stats / Visualizations",
        summary="A preserved collection of older similarity, bias, creator, and player trend plots from the first trivia-stats site.",
    ),
)


PLAYER_NAMES = (
    "Alex",
    "Chris",
    "Dad",
    "Drew",
    "Ichigo",
    "Jeff",
    "Jenny",
    "Megan",
    "Mom",
    "Zach",
)


def _blend_channel(start: int, end: int, weight: float) -> int:
    return round(start + (end - start) * weight)


def _blend_hex(start: str, end: str, weight: float) -> str:
    weight = max(0.0, min(1.0, weight))
    start_rgb = tuple(int(start[index:index + 2], 16) for index in (1, 3, 5))
    end_rgb = tuple(int(end[index:index + 2], 16) for index in (1, 3, 5))
    mixed = tuple(_blend_channel(left, right, weight) for left, right in zip(start_rgb, end_rgb))
    return "#" + "".join(f"{channel:02x}" for channel in mixed)


def _build_figure_entries(
    *,
    static_prefix: str,
    names: tuple[str, ...],
    alt_template: str,
    caption_template: str,
):
    return [
        {
            "player": player_name,
            "filename": f"unnamed-chunk-8-{index}.png",
            "static_prefix": static_prefix,
            "alt": alt_template.format(player=player_name),
            "caption": caption_template.format(player=player_name),
        }
        for index, player_name in enumerate(names, start=1)
    ]


def get_blog_index_context():
    return {
        "blog_posts": BLOG_POSTS,
    }


def get_joker_stats_blog_context():
    return {
        "creator_boxplots": _build_figure_entries(
            static_prefix="GPTrivia/img/blog/joker-stats",
            names=PLAYER_NAMES,
            alt_template="Distribution of scores by creator for {player}.",
            caption_template="{player}: score distributions grouped by round creator.",
        ),
    }


def get_other_trivia_plots_blog_context():
    return {
        "player_trend_figures": _build_figure_entries(
            static_prefix="GPTrivia/img/blog/other-trivia-plots",
            names=PLAYER_NAMES,
            alt_template="Final score trend chart for {player}.",
            caption_template="{player}: weekly final scores from the original post.",
        ),
    }


def get_roboalex_blog_context():
    all_values = [value for row in ROBOALEX_COVARIANCE_ROWS for value in row.values]
    minimum = min(all_values)
    maximum = max(all_values)
    span = maximum - minimum or 1.0

    rows = []
    for row in ROBOALEX_COVARIANCE_ROWS:
        cells = []
        for value in row.values:
            strength = (value - minimum) / span
            background = _blend_hex("#edf6ea", "#228b22", strength)
            text_color = "#ffffff" if strength >= 0.72 else "#15301c"
            cells.append(
                {
                    "value": f"{value:.2f}",
                    "background": background,
                    "text_color": text_color,
                }
            )
        rows.append({"label": row.label, "cells": cells})

    return {
        "covariance_columns": ROBOALEX_COVARIANCE_COLUMNS,
        "covariance_rows": rows,
    }
