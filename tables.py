import io
from typing import List, Any

import plotly.figure_factory as ff


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
