from __future__ import annotations

import pytest

from prompt_toolkit.layout import InvalidLayoutError, Layout
from prompt_toolkit.layout.containers import Container, HSplit, VSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.mouse_handlers import MouseHandlers
from prompt_toolkit.layout.screen import Screen, WritePosition
from prompt_toolkit.layout.utils import explode_text_fragments


def test_layout_class():
    c1 = BufferControl()
    c2 = BufferControl()
    c3 = BufferControl()
    win1 = Window(content=c1)
    win2 = Window(content=c2)
    win3 = Window(content=c3)

    layout = Layout(container=VSplit([HSplit([win1, win2]), win3]))

    # Listing of windows/controls.
    assert list(layout.find_all_windows()) == [win1, win2, win3]
    assert list(layout.find_all_controls()) == [c1, c2, c3]

    # Focusing something.
    layout.focus(c1)
    assert layout.has_focus(c1)
    assert layout.has_focus(win1)
    assert layout.current_control == c1
    assert layout.previous_control == c1

    layout.focus(c2)
    assert layout.has_focus(c2)
    assert layout.has_focus(win2)
    assert layout.current_control == c2
    assert layout.previous_control == c1

    layout.focus(win3)
    assert layout.has_focus(c3)
    assert layout.has_focus(win3)
    assert layout.current_control == c3
    assert layout.previous_control == c2

    # Pop focus. This should focus the previous control again.
    layout.focus_last()
    assert layout.has_focus(c2)
    assert layout.has_focus(win2)
    assert layout.current_control == c2
    assert layout.previous_control == c1


def test_create_invalid_layout():
    with pytest.raises(InvalidLayoutError):
        Layout(HSplit([]))


def _rendered_cells(
    container: Container, width: int, height: int = 3
) -> list[tuple[int, str]]:
    """
    Cells that the renderer would actually draw on the first row.

    ``prompt_toolkit/renderer.py`` walks the row with ``c += char_width or 1``,
    so the cells covered by a wide cell are never drawn. Mirror that here: a
    character that got overwritten by a wide cluster stays invisible in a test
    that just inspects the row cell by cell.
    """
    screen = Screen()
    Layout(container=container).container.write_to_screen(
        screen,
        MouseHandlers(),
        WritePosition(xpos=0, ypos=0, width=width, height=height),
        parent_style="",
        erase_bg=False,
        z_index=None,
    )

    row = screen.data_buffer[0]
    cells: list[tuple[int, str]] = []
    x = 0
    c = 0
    while c < width:
        char = row[c]
        cell_width = char.width or 1
        if char.char:
            cells.append((x, char.char))
        x += cell_width
        c += cell_width

    return [cell for cell in cells if cell[1] != " "]


def test_variation_selector_split_across_fragments():
    """
    A VS16 can end up in another fragment than its base character (a style
    boundary between them). It must still claim the second column of that
    cell: otherwise the next character is written into that column and is
    skipped by the renderer.
    """
    window = Window(
        FormattedTextControl([("class:a", "ab⚠"), ("class:b", "\ufe0fcd")]),
        wrap_lines=True,
    )

    assert _rendered_cells(window, 20) == [
        (0, "a"),
        (1, "b"),
        (2, "⚠️"),
        (4, "c"),
        (5, "d"),
    ]


def test_variation_selector_occupies_two_columns():
    """
    A cluster made of a base character plus VS16 must be one cell that is two
    columns wide, exactly like the terminal renders it. When the code points
    are measured separately (1 + 0), our model ends up one column narrower
    than the terminal: the terminal wraps the line and leaves characters from
    the previous frame behind.
    """
    text = "x  ⚠️ y"

    window = Window(FormattedTextControl(text), wrap_lines=True)
    screen = Screen()
    Layout(container=window).container.write_to_screen(
        screen,
        MouseHandlers(),
        WritePosition(xpos=0, ypos=0, width=40, height=3),
        parent_style="",
        erase_bg=False,
        z_index=None,
    )

    row = screen.data_buffer[0]
    cells: list[tuple[int, str]] = []
    x = 0
    for i in range(40):
        if row[i].char:
            cells.append((x, row[i].char))
        x += row[i].width

    # The two code points are one cell of width 2.
    assert (3, "⚠️") in cells
    assert row[3].width == 2

    # The following characters sit on the column where the terminal puts them:
    # "x  " is 3 columns, the "⚠️" cluster covers columns 3-4, the space
    # is column 5, so "y" starts at column 6.
    assert [col for col, char in cells if char == "y"] == [6]

    # Exploding into code points is unrelated to the screen model (it is used
    # by processors that index by code point position).
    assert len(explode_text_fragments([("", text)])) == len(text)


def test_variation_selector_wraps_as_one_cell():
    """
    A 2 column cluster that doesn't fit is wrapped, and the characters after
    it are placed next to the cell instead of overlapping it.
    """
    window = Window(FormattedTextControl("aaaa⚠️b"), wrap_lines=True)
    screen = Screen()
    Layout(container=window).container.write_to_screen(
        screen,
        MouseHandlers(),
        WritePosition(xpos=0, ypos=0, width=5, height=2),
        parent_style="",
        erase_bg=False,
        z_index=None,
    )

    def line(y: int) -> list[tuple[int, str]]:
        cells = []
        x = 0
        for i in range(5):
            if screen.data_buffer[y][i].char:
                cells.append((x, screen.data_buffer[y][i].char))
            x += screen.data_buffer[y][i].width
        return cells

    assert line(0)[:4] == [(0, "a"), (1, "a"), (2, "a"), (3, "a")]

    # The cluster took two columns on the wrapped line and "b" follows it.
    assert line(1)[:2] == [(0, "⚠️"), (2, "b")]
