class MarkupTable:
    """
    Container for holding table data and render the data in creole markup.
    Format every cell width to the same col width.
    """

    def __init__(self, head_prefix="= ", auto_width=True, debug_msg=None):
        self.head_prefix = head_prefix
        self.auto_width = auto_width

        if debug_msg is None:
            self.debug_msg = self._non_debug
        else:
            self.debug_msg = debug_msg

        self.rows = []
        self.row_index = None
        self.has_header = False

    def _non_debug(self, *args):
        pass

    def add_tr(self):
        self.debug_msg("Table.add_tr", "")
        self.rows.append([])
        self.row_index = len(self.rows) - 1

    def add_th(self, text):
        self.has_header = True
        self.add_td(self.head_prefix + text)

    def add_td(self, text):
        if self.row_index is None:
            self.add_tr()

        self.debug_msg("Table.add_td", text)
        self.rows[self.row_index].append(text)

    def _get_preformat_info(self):
        cells = []
        for row in self.rows:
            line_cells = []
            for cell in row:
                cell = cell.strip()
                if cell != "":
                    if self.head_prefix and cell.startswith(self.head_prefix):
                        cell += " "  # Headline
                    else:
                        cell = f" {cell} "  # normal cell
                line_cells.append(cell)
            cells.append(line_cells)

        # Build a list of max len for every column
        widths = [max(map(len, col)) for col in zip(*cells)]

        return cells, widths

    def get_table_markup(self):
        """ return the table data in creole/textile markup. """
        if not self.auto_width:
            lines = []
            for row in self.rows:
                lines.append("|" + "|".join(cell for cell in row) + "|")
        else:
            # preformat every table cell
            cells, widths = self._get_preformat_info()

            # Join every line with ljust
            lines = []
            for row in cells:
                cells = [cell.ljust(width) for cell, width in zip(row, widths)]
                lines.append("|" + "|".join(cells) + "|")

        result = "\n".join(lines)

        self.debug_msg("Table.get_table_markup", result)
        return result

    def get_rest_table(self):
        """ return the table data in ReSt markup. """
        # preformat every table cell
        cells, widths = self._get_preformat_info()

        separator_line = f"+{'+'.join(('-' * width) for width in widths)}+"
        headline_separator = f"+{'+'.join(('=' * width) for width in widths)}+"

        lines = []
        for no, row in enumerate(cells):
            if no == 1 and self.has_header:
                lines.append(headline_separator)
            else:
                lines.append(separator_line)

            # Join every line with ljust
            cells = [cell.ljust(width) for cell, width in zip(row, widths)]
            lines.append("|" + "|".join(cells) + "|")

        lines.append(separator_line)

        return "\n".join(lines)


if __name__ == '__main__':
    import doctest
    print(doctest.testmod())
