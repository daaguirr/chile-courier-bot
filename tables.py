import io
import math
from typing import List, Any

import plotly.figure_factory as ff
import matplotlib.pyplot as plt
import six


def generate_image(table_raw: List[List[Any]], columns: List[str]) -> io.BytesIO:
    data_matrix = [columns, *table_raw]
    max_len = max([len(''.join(row)) for row in data_matrix])

    colorscale = [[0, '#283273'], [.5, '#f1f1f2'], [1, '#ffffff']]
    fig = ff.create_table(data_matrix, colorscale=colorscale)

    for i in range(len(fig.layout.annotations)):
        fig.layout.annotations[i].font.size = 28
    img_bytes = fig.to_image(format="png", height=50 * len(data_matrix), width=max_len * 30)
    buf = io.BytesIO(img_bytes)
    buf.seek(0)
    return buf


DPI = 300
FONT_SIZE = 14


def old_generate_image(table_raw: List[List[Any]], columns: List[str]) -> io.BytesIO:
    row_colors = ['#f1f1f2', 'w']
    header_color = '#40466e'

    if len(table_raw) == 0:
        cell_text = [['-'] * len(columns)]
    else:
        cell_text = [[str(item) for item in row] for row in table_raw]
    print(cell_text)
    # print((max(map(lambda x: len('.'.join(x)), cell_text))//2, len(table_raw)))

    figsize_x = max(map(lambda x: len('.'.join(x)), cell_text))
    figsize_x = max(figsize_x, len('.'.join(columns)))
    figsize_x = 4 * figsize_x * FONT_SIZE / DPI
    figsize_y = len(table_raw)

    figsize = (figsize_x, figsize_y)

    print(figsize)

    fig, ax = plt.subplots(figsize=figsize)
    ax.axis('off')

    mpl_table = ax.table(cellText=cell_text, bbox=[0, 0, 1, 1], colLabels=columns)

    mpl_table.auto_set_font_size(False)
    mpl_table.set_fontsize(FONT_SIZE)

    for i in range(len(columns)):
        mpl_table.auto_set_column_width(i)

    for k, cell in six.iteritems(mpl_table._cells):
        cell.set_edgecolor('w')
        if k[0] == 0 or k[1] < 0:
            cell.set_text_props(weight='bold', color='w')
            cell.set_facecolor(header_color)
        else:
            cell.set_facecolor(row_colors[k[0] % len(row_colors)])

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=DPI)
    buf.seek(0)
    return buf
