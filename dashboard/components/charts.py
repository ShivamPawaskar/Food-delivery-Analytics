"""Consistent Plotly chart builders used throughout the dashboard."""
import plotly.express as px

COLORS = ["#0F766E", "#14B8A6", "#0EA5E9", "#6366F1", "#F59E0B", "#EF4444", "#8B5CF6"]


def _style(fig, height=360):
    fig.update_layout(template="plotly_white", height=height, margin=dict(l=18, r=18, t=58, b=20),
        font=dict(family="Inter, Segoe UI, sans-serif", color="#243447"),
        title=dict(x=0.02, xanchor="left", font=dict(size=17)), colorway=COLORS,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#E8EEF2", zerolinecolor="#E8EEF2")
    return fig


def line_chart(data, x, y, title, *, color=None, y_title=None):
    fig = px.line(data, x=x, y=y, color=color, markers=True, title=title,
        labels={y: y_title or y.replace("_", " ").title()}, color_discrete_sequence=COLORS)
    return _style(fig)


def multi_line_chart(data, x, ys, title, *, y_title=None):
    fig = px.line(data, x=x, y=ys, markers=True, title=title,
        labels={"value": y_title or "Value", "variable": "Series"}, color_discrete_sequence=COLORS)
    return _style(fig)


def bar_chart(data, x, y, title, *, color=None, horizontal=False, y_title=None):
    fig = px.bar(data, x=y if horizontal else x, y=x if horizontal else y, color=color,
        orientation="h" if horizontal else "v", title=title,
        labels={y: y_title or y.replace("_", " ").title()}, color_discrete_sequence=COLORS)
    return _style(fig)


def donut_chart(data, names, values, title):
    fig = px.pie(data, names=names, values=values, hole=.58, title=title,
        color_discrete_sequence=COLORS)
    fig.update_traces(textposition="inside", textinfo="percent+label")
    return _style(fig)


def histogram(data, x, title, *, color=None, nbins=24):
    fig = px.histogram(data, x=x, color=color, nbins=nbins, title=title,
        labels={x: x.replace("_", " ").title()}, color_discrete_sequence=COLORS)
    return _style(fig)


def scatter_chart(data, x, y, title, *, color=None, hover_data=None):
    fig = px.scatter(data, x=x, y=y, color=color, hover_data=hover_data,
        title=title, opacity=.68, color_discrete_sequence=COLORS)
    return _style(fig)


def weekday_heatmap(data):
    names = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}
    if data.empty:
        return _style(px.imshow([[0]], title="Orders by weekday and hour"))
    pivot = data.pivot(index="weekday", columns="order_hour", values="total_orders").fillna(0)
    pivot = pivot.reindex(range(1, 8), fill_value=0)
    fig = px.imshow(pivot, aspect="auto", color_continuous_scale="Teal", title="Orders by weekday and hour",
        labels=dict(x="Hour of day", y="Weekday", color="Orders"))
    fig.update_yaxes(tickvals=list(range(1, 8)), ticktext=[names[i] for i in range(1, 8)])
    return _style(fig, height=330)


def daily_orders(daily):
    return line_chart(daily, "order_date", "total_orders", "Daily order volume")


def city_revenue(city):
    if city.empty:
        return _style(px.bar(title="Revenue by city"))
    city = city.sort_values("revenue", ascending=False)
    return bar_chart(city, "city", "revenue", "Revenue by city", y_title="Revenue (₹)")
