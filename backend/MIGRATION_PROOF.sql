INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Generating static SQL
INFO  [alembic.runtime.migration] Will assume transactional DDL.
BEGIN;

INFO  [alembic.runtime.migration] Running upgrade 006_create_shadow_positions -> 007_generic_execution_models, Generic Execution Models Migration
-- Running upgrade 006_create_shadow_positions -> 007_generic_execution_models

ALTER TABLE exchange_orders ADD COLUMN external_id VARCHAR(128);

ALTER TABLE exchange_orders ADD UNIQUE (external_id);

ALTER TABLE exchange_orders ADD COLUMN asset_id VARCHAR(128);

ALTER TABLE exchange_orders ADD COLUMN input_mint VARCHAR(64);

ALTER TABLE exchange_orders ADD COLUMN output_mint VARCHAR(64);

ALTER TABLE exchange_orders DROP CONSTRAINT ck_exchange_orders_outcome;

ALTER TABLE exchange_orders ALTER COLUMN outcome DROP NOT NULL;

CREATE INDEX ix_exchange_orders_external_id ON exchange_orders (external_id);

CREATE INDEX ix_exchange_orders_asset_id ON exchange_orders (asset_id);

ALTER TABLE fills ADD COLUMN external_id VARCHAR(128);

ALTER TABLE fills ADD UNIQUE (external_id);

ALTER TABLE fills DROP CONSTRAINT ck_fills_outcome;

ALTER TABLE fills ALTER COLUMN outcome DROP NOT NULL;

CREATE INDEX ix_fills_external_id ON fills (external_id);

ALTER TABLE trades ADD COLUMN asset_in VARCHAR(64);

ALTER TABLE trades ADD COLUMN asset_out VARCHAR(64);

ALTER TABLE trades ALTER COLUMN outcome DROP NOT NULL;

UPDATE alembic_version SET version_num='007_generic_execution_models' WHERE alembic_version.version_num = '006_create_shadow_positions';

COMMIT;
