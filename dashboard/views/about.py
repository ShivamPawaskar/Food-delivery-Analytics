import streamlit as st


def render(_filters=None):
    st.title("About the project")
    st.markdown("""
    **Food Delivery Analytics & Visualization System** explores order, restaurant, customer,
    and delivery operations through a PostgreSQL-backed Streamlit dashboard.

    The reproducible synthetic source data represents food delivery activity across Indian
    cities. The ETL pipeline validates source rows, calculates delivery measures, enriches
    orders with restaurant and partner details, and preserves rejected records for review.
    This dashboard queries the PostgreSQL tables directly; it does not substitute local
    files or sample values when the database is unavailable.
    """)
    st.subheader("How the analytics flow works")
    st.markdown("""
    <div class="flow-wrap">
      <div class="flow-step"><div class="flow-num">1</div><div class="flow-title">Source data</div><div class="flow-copy">Orders, restaurants and delivery partners enter the pipeline.</div></div>
      <div class="flow-step"><div class="flow-num">2</div><div class="flow-title">Validate & transform</div><div class="flow-copy">ETL checks records, enriches orders and isolates rejected rows.</div></div>
      <div class="flow-step"><div class="flow-num">3</div><div class="flow-title">PostgreSQL</div><div class="flow-copy">Accepted orders, aggregates and audit results are stored.</div></div>
      <div class="flow-step"><div class="flow-num">4</div><div class="flow-title">Live dashboard</div><div class="flow-copy">SQL queries power filtered charts, KPIs and reports.</div></div>
    </div>
    """, unsafe_allow_html=True)
    st.subheader("Business definitions")
    st.markdown("""
    - **Preparation time:** pickup minus acceptance, in minutes.
    - **Delivery time:** delivery minus pickup, in minutes; delivered orders only.
    - **Fulfilment time:** delivery minus order, in minutes; delivered orders only.
    - **Late delivery:** fulfilment time exceeds promised delivery minutes.
    - **Revenue and average order value:** delivered orders only.
    - **Repeat customer:** at least two validated orders in the selected filters.
    """)
    st.subheader("Run locally")
    st.code("python -m database.setup --create-database\npython -m etl.pipeline --load-to-database\nstreamlit run dashboard/app.py", language="bash")
    st.caption("City charts use city labels. No map is shown because the source data does not include verified coordinates.")
