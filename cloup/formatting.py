import shutil
from itertools import chain
from typing import (
    Any, Callable, Dict, Iterable, NamedTuple, Optional, Sequence, Tuple, cast,
)

import click
from click.formatting import iter_rows, wrap_text

from cloup._util import check_positive_int, make_repr

# It's not worth it to require typing_extensions just define this as a Protocol.
FormatterMaker = Callable[..., 'HelpFormatter']

FORMATTER_TYPE_ERROR = """
since cloup v0.8.0, this class relies on cloup.HelpFormatter to align help
sections. So, you need to make sure your command class uses cloup.HelpFormatter
as formatter class.

If you have your own custom HelpFormatter, know that cloup.HelpFormatter is
more easily customizable then Click's one, so consider extending it instead
of extending click.HelpFormatter.
"""


def ensure_is_cloup_formatter(formatter: click.HelpFormatter) -> 'HelpFormatter':
    if isinstance(formatter, HelpFormatter):
        return formatter
    raise TypeError(FORMATTER_TYPE_ERROR)


class HelpSection(NamedTuple):
    """A container for a help section data."""
    heading: str

    #: Rows with 2 columns each.
    definitions: Sequence[Tuple[str, str]]

    #: Optional long description of the section.
    description: Optional[str] = None


# noinspection PyMethodMayBeStatic
class HelpFormatter(click.HelpFormatter):
    """
    A custom help formatter.

    .. versionadded:: 0.8.0

    :param indent_increment:
        indentation width
    :param width:
        content line width; by default it's initialized as the minimum of
        the terminal width and the argument ``max_width``.
    :param max_width:
        maximum content line width (corresponds to ``Context.max_content_width``.
        Used to compute ``width`` if it is not provided; ignored otherwise.
    :param col1_max_width:
        the maximum width of the first column of a definition list.
    :param col_spacing:
        the (minimum) number of spaces between the columns of a definition list.
    :param row_sep:
        a string printed after each row of a definition list (including the last).
    """

    def __init__(
        self, indent_increment: int = 2,
        width: Optional[int] = None,
        max_width: Optional[int] = 80,
        col1_max_width: int = 30,
        col2_min_width: int = 20,
        col_spacing: int = 2,
        row_sep: str = '',
    ):
        check_positive_int(col1_max_width, 'col1_max_width')
        check_positive_int(col_spacing, 'col_spacing')
        self.col1_max_width = col1_max_width
        self.col2_min_width = col2_min_width
        self.col_spacing = col_spacing
        self.row_sep = row_sep
        max_width = max_width or 80
        width = (
            width or click.formatting.FORCED_WIDTH
            or min(max_width, shutil.get_terminal_size((80, 100)).columns)
        )
        super().__init__(indent_increment=indent_increment,
                         width=width, max_width=max_width)

    @staticmethod
    def opts(
        *, width: Optional[int] = None,
        max_width: Optional[int] = None,
        indent_increment: Optional[int] = None,
        col1_max_width: Optional[int] = None,
        col2_min_width: Optional[int] = None,
        col_spacing: Optional[int] = None,
        row_sep: Optional[str] = None,
    ) -> Dict[str, Any]:
        """A utility method for creating a ``formatter_opts`` dictionary to
        pass as context settings or command attribute. This method exists for
        one only reason: it enables auto-complete for formatter options, thus
        improving the developer experience."""
        return {key: val for key, val in locals().items()
                if val is not None}

    def write_many_sections(
        self, sections: Sequence[HelpSection],
        aligned: bool = True,
        col2_overflow_strategy: str = "wrap",
    ) -> None:
        kwargs = dict(col2_overflow_strategy=col2_overflow_strategy)
        if aligned:
            return self.write_aligned_sections(sections, **kwargs)  # type: ignore
        for s in sections:
            self.write_section(s, **kwargs)  # type: ignore

    def write_aligned_sections(
        self, sections: Sequence[HelpSection],
        col2_overflow_strategy: str = "wrap",
    ) -> None:
        """Writes multiple aligned definition lists."""
        col1_strings = chain.from_iterable(
            (row[0] for row in dl.definitions)
            for dl in sections
        )
        col1_width = self.compute_col_width(col1_strings, self.col1_max_width)
        for s in sections:
            self.write_section(
                s, col1_width=col1_width,
                col2_overflow_strategy=col2_overflow_strategy)

    def write_section(self, s: HelpSection, **write_dl_kwargs) -> None:
        with self.section(s.heading):
            if s.description:
                self.write_text(s.description)
                if self.row_sep:
                    self.write(self.row_sep)
            self.write_dl(s.definitions, **write_dl_kwargs)

    def compute_col_width(self, strings: Iterable[str], max_width: int) -> int:
        lengths_under_limit = (length for length in map(len, strings)
                               if length <= max_width)
        return max(lengths_under_limit, default=0)

    def determine_col_widths(
        self,
        col1_width: Optional[int] = None,
        rows: Optional[Iterable[Tuple[str, str]]] = None,
        col1_max_width: Optional[int] = None,
        col_spacing: Optional[int] = None,
    ) -> Tuple[int, int]:
        """
        Determines the column widths of a definition list. You must provide at
        least one of ``col1_width`` and ``rows``. The default implementation
        ignore ``rows`` if ``col1_width`` is provided.

        :param col1_width:
            the desired value for the 1st column; if provided, ``col1_strings``
            is ignored.
        :param rows:
            iterable of pair of strings; the default implementation ignore this
            argument if ``col1_width`` is provided.
        :param col1_max_width:
            if provided, overrides ``self.col1_max_width``.
        :param col_spacing:
            if provided, overrides ``self.col_spacing``.
        :return: ``(col1_width, col_spacing, col2_width)``
        """
        if not (col1_width or rows):
            raise ValueError(
                'at least one of col1_width and col1_strings must be provided')

        # Compute 1st column width
        width = cast(int, self.width)
        available_width = width - self.current_indent
        actual_col1_max_width = min(
            col1_max_width or self.col1_max_width,
            available_width,
        )
        col1_width = min(
            col1_width
            or self.compute_col_width((r[0] for r in rows), actual_col1_max_width),
            actual_col1_max_width
        )
        # Derive 2nd column width
        col_spacing = col_spacing or self.col_spacing
        col2_width = available_width - col1_width - col_spacing
        return col1_width, col2_width

    def write_dl(  # type: ignore
        self, rows: Sequence[Tuple[str, str]],
        col_max: Optional[int] = None,  # default changed to None wrt parent class
        col_spacing: Optional[int] = None,  # default changed to None wrt parent class
        col1_width: Optional[int] = None,
        col2_min_width: Optional[int] = None,
        col2_overflow_strategy: str = 'wrap',
    ) -> None:
        """Writes a definition list into the buffer. This is how options
        and commands are usually formatted.

        If there's enough space, definition lists are rendered as a 2-column
        pseudo-table: if the first column text of a row doesn't fit in the
        provided/computed ``col1_width``, the 2nd column is printed on the
        following line.

        If the available space for the 2nd column is below ``self.col2_min_width``,
        the definition list is rendered as a linear list with each "column"
        printed on its own line and the 2nd column indented with 4 spaces.

        :param rows:
            a list of two item tuples for the terms and values.
        :param col_max:
            the maximum width for the 1st column of a definition list; this
            argument is here to not break compatibility with Click; if provided,
            it overrides the attribute ``self.col1_max_width``.
        :param col_spacing:
            number of spaces between the first and second column;
            this argument is here to not break compatibility with Click;
            if provided, it overrides ``self.col_spacing``.
        :param col1_width:
            the width to use for the first column; if not provided, it's
            computed as the length of the longest string under ``self.col1_max_width``;
            useful when you need to align multiple definition lists.
        :param col2_min_width:
            the minimum width for the 2nd column; if the available space for the
            2nd column is below this threshold, the definition list is printed as
            a "linear" list, not as a 2-column table.
        :param col2_overflow_strategy:
            if "wrap", the text is wrapped in multiple lines and shown;
            if "truncate", the text is truncated to fit a single line.
        """
        if col2_overflow_strategy not in {"wrap", "truncate"}:
            raise ValueError(f"invalid col2_overflow_strategy: {col2_overflow_strategy}")

        # |<----------------------- width ------------------------>|
        # |                |<---------- available_width ---------->|
        # | current_indent | col1_width | col_spacing | col2_width |

        col_spacing = col_spacing or self.col_spacing
        col1_width, col2_width = self.determine_col_widths(
            col1_width=col1_width,
            rows=rows,
            col1_max_width=col_max,
            col_spacing=col_spacing,
        )

        if col2_width < self.col2_min_width:
            self.write_linear_dl(rows, col2_overflow_strategy)
        else:
            self.write_tabular_dl(
                rows, col1_width, col_spacing, col2_width,
                col2_overflow_strategy
            )

    def write_tabular_dl(
        self, rows, col1_width, col_spacing, col2_width,
        col2_overflow_strategy,
    ) -> None:
        wrap_overflow = (col2_overflow_strategy == "wrap")
        col1_plus_spacing_width = col1_width + col_spacing

        current_indentation = " " * self.current_indent
        col2_indentation = " " * (
            self.current_indent + max(self.indent_increment, col1_plus_spacing_width)
        )

        for first, second in iter_rows(rows, col_count=2):
            self.write(current_indentation)
            self.write(first)
            if not second:
                self.write('\n')
                self.write(self.row_sep)
                continue

            if len(first) <= col1_width:
                spaces_to_col2 = col1_plus_spacing_width - len(first)
                self.write(" " * spaces_to_col2)
            else:
                self.write("\n")
                self.write(col2_indentation)

            if wrap_overflow:
                wrapped_text = wrap_text(second, col2_width, preserve_paragraphs=True)
                lines = wrapped_text.splitlines()
                self.write(lines[0] + "\n")
                for line in lines[1:]:
                    self.write(f"{col2_indentation}{line}\n")
            else:
                truncated = truncate_text(second, col2_width)
                self.write(truncated)
                self.write("\n")

            if self.row_sep:
                self.write(self.row_sep)

    def write_linear_dl(
        self, rows: Sequence[Tuple[str, str]],
        overflow_strategy = 'wrap',
    ) -> None:
        descr_max_width = self.width - self.current_indent - self.indent_increment
        indentation = " " * self.current_indent
        descr_indentation = " " * (self.current_indent + 4)
        wrap_overflow = overflow_strategy == "wrap"

        for names, descr in iter_rows(rows, col_count=2):
            self.write(indentation + names + '\n')
            if descr:
                if wrap_overflow:
                    self.current_indent += 4
                    self.write_text(descr)
                    self.current_indent -= 4
                else:
                    truncated = truncate_text(descr, descr_max_width)
                    self.write(descr_indentation + truncated + "\n")
            self.write("\n")
        self.buffer.pop()

    def __repr__(self):
        return make_repr(
            self, width=self.width, indent_increment=self.indent_increment,
            col1_max_width=self.col1_max_width, col_spacing=self.col_spacing
        )

    def getvalue(self):
        """Returns the buffer contents."""
        return "".join(self.buffer)


def truncate_text(text: str, max_length: int, placeholder: str = "...") -> str:
    text = " ".join(text.split())
    if len(text) <= max_length:
        return text
    max_cut_point = max(max_length - len(placeholder) + 1, 0)
    end = text.rfind(" ", 0, max_cut_point)
    if end == -1:
        return ""
    return text[:end] + placeholder
