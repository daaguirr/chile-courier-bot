import io
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


def old_generate_image(table_raw: List[List[Any]], columns: List[str]) -> io.BytesIO:
    row_colors = ['#f1f1f2', 'w']
    header_color = '#40466e'

    fig, ax = plt.subplots(figsize=(len(columns)*3, len(table_raw)))
    ax.axis('off')

    cell_text = [[str(item) for item in row] for row in table_raw]

    mpl_table = ax.table(cellText=cell_text, bbox=[0, 0, 1, 1], colLabels=columns)

    mpl_table.auto_set_font_size(False)
    mpl_table.set_fontsize(14)

    for k, cell in six.iteritems(mpl_table._cells):
        cell.set_edgecolor('w')
        if k[0] == 0 or k[1] < 0:
            cell.set_text_props(weight='bold', color='w')
            cell.set_facecolor(header_color)
        else:
            cell.set_facecolor(row_colors[k[0] % len(row_colors)])

    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)
    return buf
