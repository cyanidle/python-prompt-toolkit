from __future__ import annotations

import itertools

import pytest

from prompt_toolkit.utils import (
    get_cursor_column,
    get_cwidth,
    split_char_clusters,
    take_using_weights,
)


def test_get_cwidth_variation_selector():
    # VS16 (U+FE0F) selects the emoji presentation of its base character,
    # which is two columns wide for a narrow base character.
    assert get_cwidth("⚠") == 1
    assert get_cwidth("⚠️") == 2
    assert get_cwidth("a⚠️b") == 4

    # A base character that is wide by itself stays two columns.
    assert get_cwidth("⌚") == 2
    assert get_cwidth("⌚️") == 2

    # A combining accent never changes the width of its base character.
    assert get_cwidth("e\u0301") == 1


def test_split_char_clusters():
    # Without variation selectors, the string is returned as is.
    assert split_char_clusters("") == ""
    assert split_char_clusters("abc") == "abc"

    # A base character keeps the variation selectors that follow it.
    assert split_char_clusters("a⚠️b") == ["a", "⚠️", "b"]
    assert split_char_clusters("⚠\ufe0e") == ["⚠\ufe0e"]

    # A variation selector without a base character is its own cluster.
    assert split_char_clusters("\ufe0f") == ["\ufe0f"]


def test_get_cursor_column_inside_cluster():
    line = "x  ⚠️ y"  # 3 4 are the code points of the cluster.

    # Cursor before, inside and after the cluster.
    assert get_cursor_column(line, 3) == 3
    assert get_cursor_column(line, 4) == 3
    assert get_cursor_column(line, 5) == 5

    # Consecutive variation selectors are all part of the same cluster.
    assert get_cursor_column("⚠\ufe0f\ufe0f", 1) == 0
    assert get_cursor_column("⚠\ufe0f\ufe0f", 2) == 0

    # A cursor at the end of the string counts the whole string.
    assert get_cursor_column("⚠️", 2) == 2

    # Without variation selectors: the width of the prefix.
    assert get_cursor_column("abc", 0) == 0
    assert get_cursor_column("abc", 2) == 2
    assert get_cursor_column("abc", 3) == 3


def test_using_weights():
    def take(generator, count):
        return list(itertools.islice(generator, 0, count))

    # Check distribution.
    data = take(take_using_weights(["A", "B", "C"], [5, 10, 20]), 35)
    assert data.count("A") == 5
    assert data.count("B") == 10
    assert data.count("C") == 20

    assert data == [
        "A",
        "B",
        "C",
        "C",
        "B",
        "C",
        "C",
        "A",
        "B",
        "C",
        "C",
        "B",
        "C",
        "C",
        "A",
        "B",
        "C",
        "C",
        "B",
        "C",
        "C",
        "A",
        "B",
        "C",
        "C",
        "B",
        "C",
        "C",
        "A",
        "B",
        "C",
        "C",
        "B",
        "C",
        "C",
    ]

    # Another order.
    data = take(take_using_weights(["A", "B", "C"], [20, 10, 5]), 35)
    assert data.count("A") == 20
    assert data.count("B") == 10
    assert data.count("C") == 5

    # Bigger numbers.
    data = take(take_using_weights(["A", "B", "C"], [20, 10, 5]), 70)
    assert data.count("A") == 40
    assert data.count("B") == 20
    assert data.count("C") == 10

    # Negative numbers.
    data = take(take_using_weights(["A", "B", "C"], [-20, 10, 0]), 70)
    assert data.count("A") == 0
    assert data.count("B") == 70
    assert data.count("C") == 0

    # All zero-weight items.
    with pytest.raises(ValueError):
        take(take_using_weights(["A", "B", "C"], [0, 0, 0]), 70)
