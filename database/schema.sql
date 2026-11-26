CREATE TABLE IF NOT EXISTS restaurants (
    restaurant_id TEXT PRIMARY KEY,
    restaurant_name TEXT NOT NULL,
    cuisine TEXT NOT NULL,
    city TEXT NOT NULL,
    restaurant_rating NUMERIC(2,1) CHECK (restaurant_rating BETWEEN 0 AND 5),
    average_prep_minutes INTEGER CHECK (average_prep_minutes > 0)
);

CREATE TABLE IF NOT EXISTS delivery_partners (
    partner_id TEXT PRIMARY KEY,
    partner_name TEXT NOT NULL,
    vehicle_type TEXT NOT NULL,
    partner_rating NUMERIC(2,1) CHECK (partner_rating BETWEEN 0 AND 5),
    partner_city TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS etl_audit (
    execution_id UUID PRIMARY KEY,
    execution_timestamp TIMESTAMPTZ NOT NULL,
    execution_status TEXT NOT NULL,
    execution_duration_seconds NUMERIC(12,4),
    source_row_counts JSONB NOT NULL,
    valid_row_count INTEGER NOT NULL CHECK (valid_row_count >= 0),
    rejected_row_count INTEGER NOT NULL CHECK (rejected_row_count >= 0),
    transformation_counts JSONB NOT NULL,
    rejection_reason_counts JSONB NOT NULL,
    raw_sources_unchanged BOOLEAN,
    database_load_status TEXT NOT NULL DEFAULT 'not_requested',
    database_loaded_row_counts JSONB NOT NULL DEFAULT '{}'::jsonb,
    error TEXT
);

CREATE TABLE IF NOT EXISTS processed_orders (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    restaurant_id TEXT NOT NULL REFERENCES restaurants(restaurant_id),
    partner_id TEXT NOT NULL REFERENCES delivery_partners(partner_id),
    order_timestamp TIMESTAMP NOT NULL,
    accepted_timestamp TIMESTAMP,
    pickup_timestamp TIMESTAMP,
    delivered_timestamp TIMESTAMP,
    order_amount NUMERIC(10,2) NOT NULL CHECK (order_amount > 0),
    delivery_fee NUMERIC(8,2) NOT NULL CHECK (delivery_fee >= 0),
    payment_method TEXT NOT NULL,
    order_status TEXT NOT NULL CHECK (order_status IN ('delivered', 'cancelled', 'failed')),
    promised_delivery_minutes INTEGER NOT NULL CHECK (promised_delivery_minutes > 0),
    delivery_distance_km NUMERIC(6,1) NOT NULL CHECK (delivery_distance_km > 0),
    city TEXT NOT NULL,
    prep_time_minutes NUMERIC(10,2),
    delivery_time_minutes NUMERIC(10,2),
    total_fulfilment_minutes NUMERIC(10,2),
    order_date DATE NOT NULL,
    order_month TEXT NOT NULL,
    order_hour SMALLINT NOT NULL CHECK (order_hour BETWEEN 0 AND 23),
    is_late BOOLEAN NOT NULL,
    restaurant_name TEXT NOT NULL,
    cuisine TEXT NOT NULL,
    restaurant_rating NUMERIC(2,1),
    restaurant_city TEXT NOT NULL,
    partner_name TEXT NOT NULL,
    vehicle_type TEXT NOT NULL,
    partner_rating NUMERIC(2,1),
    partner_city TEXT NOT NULL,
    revenue NUMERIC(12,2) NOT NULL CHECK (revenue >= 0),
    CONSTRAINT delivered_metrics_present CHECK (
        (order_status = 'delivered' AND delivered_timestamp IS NOT NULL AND delivery_time_minutes IS NOT NULL AND total_fulfilment_minutes IS NOT NULL)
        OR (order_status <> 'delivered' AND delivery_time_minutes IS NULL AND total_fulfilment_minutes IS NULL)
    )
);

CREATE TABLE IF NOT EXISTS rejected_records (
    rejected_record_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    execution_id UUID NOT NULL REFERENCES etl_audit(execution_id) ON DELETE CASCADE,
    source_row_number INTEGER NOT NULL CHECK (source_row_number > 1),
    source_record_hash TEXT NOT NULL,
    original_record JSONB NOT NULL,
    rejection_reason TEXT NOT NULL,
    validation_category TEXT NOT NULL,
    processing_timestamp TIMESTAMPTZ NOT NULL,
    UNIQUE (execution_id, source_row_number),
    UNIQUE (execution_id, source_record_hash)
);

CREATE TABLE IF NOT EXISTS daily_performance (
    order_date DATE PRIMARY KEY,
    total_orders INTEGER NOT NULL,
    completed_orders INTEGER NOT NULL,
    cancelled_orders INTEGER NOT NULL,
    revenue NUMERIC(14,2) NOT NULL,
    average_order_value NUMERIC(12,2),
    average_delivery_time NUMERIC(10,2),
    late_deliveries INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS restaurant_performance (
    restaurant_id TEXT PRIMARY KEY REFERENCES restaurants(restaurant_id),
    restaurant_name TEXT NOT NULL,
    total_orders INTEGER NOT NULL,
    revenue NUMERIC(14,2) NOT NULL,
    average_order_value NUMERIC(12,2),
    average_preparation_time NUMERIC(10,2),
    average_delivery_time NUMERIC(10,2),
    late_delivery_percentage NUMERIC(6,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS city_performance (
    city TEXT PRIMARY KEY,
    total_orders INTEGER NOT NULL,
    revenue NUMERIC(14,2) NOT NULL,
    average_delivery_time NUMERIC(10,2),
    cancellation_rate NUMERIC(6,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS cuisine_performance (
    cuisine TEXT PRIMARY KEY,
    total_orders INTEGER NOT NULL,
    revenue NUMERIC(14,2) NOT NULL,
    average_order_value NUMERIC(12,2)
);

CREATE TABLE IF NOT EXISTS delivery_partner_performance (
    partner_id TEXT PRIMARY KEY REFERENCES delivery_partners(partner_id),
    partner_name TEXT NOT NULL,
    total_deliveries INTEGER NOT NULL,
    average_delivery_time NUMERIC(10,2),
    partner_rating NUMERIC(2,1),
    late_delivery_percentage NUMERIC(6,2) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_processed_orders_timestamp ON processed_orders(order_timestamp);
CREATE INDEX IF NOT EXISTS idx_processed_orders_date ON processed_orders(order_date);
CREATE INDEX IF NOT EXISTS idx_processed_orders_city_date ON processed_orders(city, order_date);
CREATE INDEX IF NOT EXISTS idx_processed_orders_status_date ON processed_orders(order_status, order_date);
CREATE INDEX IF NOT EXISTS idx_processed_orders_restaurant_date ON processed_orders(restaurant_id, order_date);
CREATE INDEX IF NOT EXISTS idx_processed_orders_partner_date ON processed_orders(partner_id, order_date);
CREATE INDEX IF NOT EXISTS idx_processed_orders_cuisine_date ON processed_orders(cuisine, order_date);
CREATE INDEX IF NOT EXISTS idx_rejected_records_execution ON rejected_records(execution_id);
CREATE INDEX IF NOT EXISTS idx_etl_audit_timestamp ON etl_audit(execution_timestamp DESC);
