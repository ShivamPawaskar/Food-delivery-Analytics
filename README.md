# Food Delivery Analytics & Visualization System

## 1. Introduction and problem statement

Food delivery platforms need to understand order demand, revenue, restaurant quality, delivery speed, customer activity, and data reliability across cities. This academic project demonstrates a complete analytics workflow: reproducible synthetic source data, auditable ETL, relational PostgreSQL storage, SQL analytics, business insights, and an interactive React dashboard backed by a Python API.

The source is synthetic and generated for this project. No external dataset, API, customer account, or live delivery service is used.

## 2. Objectives

- Generate related, reproducible Indian food delivery datasets.
- Detect and preserve source data problems instead of hiding them.
- Transform valid orders into analyzable, enriched records.
- Load facts, dimensions, aggregates, rejected rows, and ETL audit data into PostgreSQL.
- Calculate operational KPIs and generate evidence-based business observations.
- Provide a modular dashboard and downloadable CSV/PDF reports.

## 3. Features

- Seeded Pandas/NumPy dataset generator and automatic data profile.
- Extract, validate, transform, aggregate, and audit ETL pipeline.
- PostgreSQL schema, transactional bulk upsert, snapshot synchronization, and consistency checks.
- Parameterized SQL analytics with date and categorical filters.
- Daily and monthly moving averages and revenue growth.
- A PostgreSQL-backed 7/14-day weekday demand forecast with rolling 28-day holdout scores against a same-weekday baseline and empirical error bands.
- Calendar order heatmap, restaurant rating/revenue quadrant, city-by-vehicle delivery comparison, and order outcome flow visualization.
- Rule-based business insights whose evidence comes from PostgreSQL query results.
- A responsive React dashboard with PostgreSQL-backed overview, orders, restaurants, delivery, customers, an interactive city activity map, data quality, ETL monitoring, CSV file analysis, exports, and project information.
- Filtered CSV exports, a complete CSV report ZIP, and a summary PDF.
- Unit and optional PostgreSQL integration tests.

## 4. Technology stack

| Area | Technology |
|---|---|
| Data generation and ETL | Python, Pandas, NumPy |
| Database | PostgreSQL, SQLAlchemy, psycopg2 |
| Dashboard and charts | React, Vite, Recharts, custom responsive UI |
| Analytics API | FastAPI, SQLAlchemy, PostgreSQL |
| Reports | Pandas CSV/ZIP, ReportLab PDF |
| Tests | pytest |

## 5. Architecture

```text
generate_dataset.py
        │
        ├── data/raw/*.csv ──> etl.extract
        │                         │
        │                  validate / transform
        │                         │
        ├── data/reports/ <── audit + profiling
        │                         │
        └── data/processed/*.csv <┘
                                  │
                           database.loader
                                  │
              PostgreSQL dimensions, facts, aggregates,
              rejected_records, and etl_audit
                                  │
          parameterized database.queries / insights engine
                                  │
                   FastAPI analytics API
                                  │
                       React dashboard
```

## 6. Project structure

```text
analytics/                 Metrics, evidence-based insights, CSV/PDF reports
config/                    Environment-aware paths and settings
api/
  app.py                   Read-only API for live PostgreSQL analytics
  run_local.py              Starts API and React development server together
frontend/
  src/main.jsx             React screens, filters, search, exports and charts
  src/styles.css           Responsive visual system and motion design
  vite.config.js           API proxy and frontend build configuration
dashboard/                  Retained Streamlit implementation
database/
  schema.sql               Relational tables, constraints, indexes
  connection.py            Engine, health-check, connection, transaction helpers
  loader.py                Transactional upserts and consistency checks
  queries.py               PostgreSQL analytics and EXPLAIN ANALYZE
  setup.py                 Database creation and schema initialization
etl/                       Extract, validate, transform, aggregate, audit, load
data/raw/                  Generated immutable source CSVs
data/processed/            Accepted, rejected, and aggregate CSVs
data/reports/              Profiles, ETL quality reports, and audit history
tests/                     Unit and optional PostgreSQL integration tests
.streamlit/config.toml     Theme and safe server defaults
generate_dataset.py        Reproducible source-data generator
run_etl_to_postgres.bat    Windows setup, ETL, load, and reconciliation
run_dashboard.bat          Windows React and API startup
JURY_GUIDE.md              Presentation walkthrough and viva preparation
```

## 7. Dataset generation and description

Run `python generate_dataset.py` to create exactly:

| File | Rows | Description |
|---|---:|---|
| `data/raw/orders.csv` | 10,000 | Orders, milestones, amount, status, payment, distance, and city |
| `data/raw/restaurants.csv` | 100 | Restaurant identity, cuisine, city, rating, preparation estimate |
| `data/raw/delivery_partners.csv` | 250 | Partner identity, vehicle, rating, and city |

The random seed defaults to `42` and can be set with `RANDOM_SEED`. Dates span approximately six months. Cities and cuisines represent the requested Indian market context. Master restaurant and partner datasets are clean. The orders source deliberately contains controlled missing values, duplicate IDs, malformed timestamps, invalid amounts/fees, unknown foreign keys, out-of-order milestones, and invalid statuses. `data/reports/dataset_profile.json` records source counts, types, nulls, unique values, summaries, and foreign-key issues.

Re-running the ETL does not modify raw files. Running the generator intentionally recreates them from the seed.

## 8. ETL, cleaning, and validation

Run the CSV-only ETL with `python -m etl.pipeline`.

1. **Extract:** checks all expected source files, encoding, nonempty contents, and required columns.
2. **Normalize:** standardizes column names, trims whitespace, maps blank strings to missing values, parses timestamps, and converts numeric fields.
3. **Validate:** checks required order fields, customer ID format, unique order IDs, restaurant/partner keys, statuses, positive amounts/distances/promised times, nonnegative fees, timestamp validity, and milestone ordering.
4. **Reject with traceability:** writes each invalid source row once with its CSV line number, original fields, every rejection reason, category, and processing timestamp.
5. **Calculate and enrich:** computes durations, date/month/hour, late flag, revenue, and many-to-one restaurant and partner joins.
6. **Aggregate:** creates daily, restaurant, city, cuisine, and delivery partner performance tables.
7. **Audit:** writes per-run execution ID, source/accepted/rejected counts, reason counts, raw-source hashes, transformations, status, and duration.

Delivery time and fulfilment time are null for non-delivered orders. Rejected rows never enter `processed_orders`.

Outputs are written to `data/processed/`: `processed_orders.csv`, compatibility `orders.csv`, `rejected_records.csv`, `daily_performance.csv`, `restaurant_performance.csv`, `city_performance.csv`, `cuisine_performance.csv`, and `delivery_partner_performance.csv`. JSON quality and audit reports are written to `data/reports/`.

## 9. PostgreSQL schema and loading

The schema defines `restaurants`, `delivery_partners`, `processed_orders`, five performance aggregate tables, `rejected_records`, and `etl_audit`. Order facts reference restaurant and partner dimensions. Aggregate restaurant and partner results reference their dimensions. Primary/unique keys, foreign keys, checks, and indexes enforce relationships and support date/city/status/restaurant/partner/cuisine queries.

Loading uses SQLAlchemy PostgreSQL `INSERT .. ON CONFLICT` bulk operations inside one transaction. It upserts current keys, removes stale snapshot keys, writes rejected rows separately as JSONB, and records the ETL execution. A failure rolls the transaction back. The loader checks unique accepted plus rejected rows against the raw source count. `database.check_data_consistency` compares CSV and PostgreSQL table counts.

## 10. SQL analytics and KPI formulas

`database/queries.py` performs filtering, joins, window calculations, and aggregation in PostgreSQL using bound parameters. It includes overall KPIs, restaurant/city/cuisine/partner comparisons, vehicle performance, customer frequency/spending, payment/status mix, peak hours, daily/monthly trends, and `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` for predefined read queries.

- **Revenue:** delivered order amount; cancelled/failed orders contribute zero.
- **Average order value:** delivered order amount total divided by delivered order count.
- **Preparation:** pickup timestamp minus accepted timestamp, in minutes.
- **Delivery:** delivered timestamp minus pickup timestamp, in minutes.
- **Fulfilment:** delivered timestamp minus order timestamp, in minutes.
- **Late:** delivered order whose fulfilment minutes exceed promised minutes.
- **Cancellation rate:** cancelled orders divided by filtered orders.
- **Repeat customer:** at least two valid orders in the selected filters; spending counts delivered orders only.
- **Daily moving average:** current day plus up to six preceding daily observations.
- **Monthly moving average:** current month plus up to two preceding monthly observations.
- **Revenue growth:** `(current revenue - previous period revenue) / previous period revenue × 100`; undefined when previous revenue is zero or absent.

## 11. Dashboard modules and filters

The primary dashboard is React, served by Vite in development and backed by the FastAPI application in `api/app.py`. Its API only exposes named SQL queries defined in `database/queries.py`; filter values are passed as bound parameters. The interface includes global filters, order search, responsive navigation, live charts, downloadable reports, ETL monitoring, and rejected record inspection. The original Streamlit application remains available with `streamlit run dashboard/app.py`.

The interactive map joins city aggregates to GeoNames WGS84 city-centre reference points documented in `frontend/CITY_COORDINATES.md`. Markers are sized by filtered order count; selecting a marker filters the dashboard. The source dataset does not contain delivery addresses, customer coordinates, restaurant coordinates, or driver GPS. The animated restaurant-to-customer delivery journey is illustrative, not a live route. Map tiles are provided by OpenStreetMap with visible attribution. The Forecast page aggregates up to 180 days of PostgreSQL history, predicts the next 7 or 14 days using a four-week weekday mean, and backtests the final 28 historical days against last-week seasonal naive. Its shaded band is the 90th-percentile absolute backtest error, not a guaranteed statistical interval. Its what-if calculator accepts user-entered order volume and average order value, then estimates completed orders and revenue using the selected data's historical completion rate. The automated report page creates live CSV exports. The older Streamlit implementation still offers its complete ZIP/PDF reporting page.

The React dashboard includes an Upload Analysis page for CSV profiling (maximum 10 MB, 100,000 rows, and 100 columns). It reports column types, missing values, duplicates, numeric summaries, distributions, and a data preview. The API processes each upload temporarily for that request and does not retain it or load it into PostgreSQL.

The dashboard also includes Dash, a small animated mascot with a guided tour across the Overview, Orders, Forecast, Restaurants, Delivery, Customers, Cities, Data Quality, ETL Monitor, Upload Analysis, Reports, and About pages. Each tour step navigates to and spotlights its relevant feature, scrolls it into view, and places Dash’s explanation beside it. Users can go back, continue, or exit at any time.

## 12. Business insights

`analytics/insights.py` applies documented rules to live PostgreSQL query results. Examples include cities with the largest order count, highest-revenue cuisine, high-cancellation cities compared with the filtered overall rate, low-rated active restaurants, high-late-delivery restaurants with a minimum sample size, strong delivery partners, and the busiest hour/meal period. Each observation includes evidence and its trigger rule. If a rule finds no matching rows, no corresponding insight is shown.

## 13. Testing methodology

Install requirements, then run `pytest`. Unit tests cover reproducibility, ETL reconciliation, raw immutability, calculations, aggregations, insight thresholds, filter normalization, CSV/ZIP exports, Plotly components, and SQL compilation. PostgreSQL integration tests are skipped unless `TEST_DATABASE_URL` points to a dedicated database ending in `_test`; they exercise database creation, schema initialization, connection, bulk upsert, idempotency, rollback/foreign keys, query execution, EXPLAIN, report generation, and Set 2 row-count consistency.

The integration fixture may create the named test database if the configured PostgreSQL user has permission. It never drops a database. Do not point `TEST_DATABASE_URL` at production or the application database.

## 14. Installation and Windows execution

From PowerShell in the project directory:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env with a PostgreSQL user/password; keep .env private.
```

Create/load PostgreSQL and verify counts:

```powershell
python -m database.setup --create-database
python generate_dataset.py
python -m etl.pipeline --load-to-database
python -m database.check_data
```

Install the React packages once, then start the dashboard (the batch file starts the API and frontend together):

```powershell
npm.cmd --prefix frontend install
run_dashboard.bat
```

Open `http://127.0.0.1:5173`. The API documentation is available at `http://127.0.0.1:8000/docs`. For frontend production assets, run `npm.cmd --prefix frontend run build`; the FastAPI server will serve `frontend/dist` when it exists.

The older Streamlit UI remains available separately:

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard\app.py
```

Run tests with:

```powershell
pytest
```

Or double-click/run `run_etl_to_postgres.bat` after creating `.venv` and `.env`, followed by `run_dashboard.bat`.

## 15. Configuration and deployment

Set `DATABASE_URL` to `postgresql+psycopg2://user:password@host:5432/food_delivery_analytics`. Set `TEST_DATABASE_URL` separately to a database whose name ends in `_test`. `.env` is git-ignored; never commit credentials. For hosted deployment, provision a reachable managed PostgreSQL database, store the URL in the hosting platform's secret manager, require TLS (`sslmode=require` where supported), restrict database network access, and use a least-privilege application role. Build the React app and run `python -m uvicorn api.app:app --host 0.0.0.0 --port 8000`. The FastAPI process serves the built `frontend/dist` site and its `/api` endpoints from the same origin. Localhost PostgreSQL is not reachable from a remote host without a secure network endpoint.

## 16. Known limitations and future work

- All orders and ratings are synthetic and are not evidence about real delivery businesses.
- Customer IDs are synthetic identifiers; no real customer-level profile or location is available.
- Delivery activity is available only at city level; no neighborhood heatmap or live route can be derived from the source records.
- PostgreSQL credentials and live database access are environment-specific; a deployment must provision them.
- Moving averages use observed daily/monthly rows; sparse periods are not expanded into a calendar spine.
- Future improvements could add a calendar table, role-based access, scheduled ETL, richer service-level targets, and verified geospatial source data.

## 17. Jury demonstration

See [JURY_GUIDE.md](JURY_GUIDE.md) for the architecture explanation, formulas, dashboard walkthrough, 30 viva questions, and a timed 5-minute presentation script.
