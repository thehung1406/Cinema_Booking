"""Frozen PostgreSQL Catalog schema: catalog, quotes and schedule bindings."""
from alembic import op

revision="catalog_001"
down_revision=None
branch_labels=None
depends_on=None


def upgrade():
    op.execute("\nCREATE TABLE films (\n\tid SERIAL NOT NULL, \n\ttitle VARCHAR(100) NOT NULL, \n\timage VARCHAR(255), \n\trating VARCHAR(10), \n\tduration_minutes INTEGER, \n\tlanguage VARCHAR(50), \n\tsubtitle VARCHAR(50), \n\trelease_date DATE, \n\tend_date DATE, \n\tdescription TEXT, \n\ttrailer VARCHAR(255), \n\tdeleted_at TIMESTAMP WITH TIME ZONE, \n\tcatalog_version INTEGER DEFAULT '1' NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT ck_film_duration_positive CHECK (duration_minutes > 0)\n)\n\n")
    op.execute('CREATE INDEX ix_films_release_end_date ON films (release_date, end_date)')
    op.execute("\nCREATE TABLE food_items (\n\tid SERIAL NOT NULL, \n\tname VARCHAR(150) NOT NULL, \n\tdescription VARCHAR(500) NOT NULL, \n\tcategory VARCHAR(20) NOT NULL, \n\tprice NUMERIC(12, 2) NOT NULL, \n\tis_active BOOLEAN NOT NULL, \n\tcatalog_version INTEGER DEFAULT '1' NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT ck_food_price CHECK (price > 0), \n\tCONSTRAINT ck_food_category CHECK (category IN ('POPCORN', 'DRINK', 'COMBO'))\n)\n\n")
    op.execute('\nCREATE TABLE food_quotes (\n\tid VARCHAR(36) NOT NULL, \n\tversion INTEGER NOT NULL, \n\tlines JSON NOT NULL, \n\ttotal NUMERIC(12, 2) NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id)\n)\n\n')
    op.execute('CREATE INDEX ix_food_quotes_expires_at ON food_quotes (expires_at)')
    op.execute('\nCREATE TABLE formats (\n\tid SERIAL NOT NULL, \n\tcode VARCHAR(20) NOT NULL, \n\tname VARCHAR(50) NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (code)\n)\n\n')
    op.execute('\nCREATE TABLE genres (\n\tid SERIAL NOT NULL, \n\tname VARCHAR(100) NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (name)\n)\n\n')
    op.execute('\nCREATE TABLE combo_items (\n\tid SERIAL NOT NULL, \n\tcombo_id INTEGER NOT NULL, \n\tfood_item_id INTEGER NOT NULL, \n\tquantity INTEGER NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_combo_component UNIQUE (combo_id, food_item_id), \n\tCONSTRAINT ck_combo_quantity CHECK (quantity > 0), \n\tCONSTRAINT ck_combo_not_self CHECK (combo_id <> food_item_id), \n\tFOREIGN KEY(combo_id) REFERENCES food_items (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(food_item_id) REFERENCES food_items (id) ON DELETE RESTRICT\n)\n\n')
    op.execute('CREATE INDEX ix_combo_items_combo_id ON combo_items (combo_id)')
    op.execute('CREATE INDEX ix_combo_items_food_item_id ON combo_items (food_item_id)')
    op.execute('\nCREATE TABLE film_formats (\n\tfilm_id INTEGER NOT NULL, \n\tformat_id INTEGER NOT NULL, \n\tPRIMARY KEY (film_id, format_id), \n\tFOREIGN KEY(film_id) REFERENCES films (id) ON DELETE CASCADE, \n\tFOREIGN KEY(format_id) REFERENCES formats (id) ON DELETE RESTRICT\n)\n\n')
    op.execute('\nCREATE TABLE film_genres (\n\tfilm_id INTEGER NOT NULL, \n\tgenre_id INTEGER NOT NULL, \n\tPRIMARY KEY (film_id, genre_id), \n\tFOREIGN KEY(film_id) REFERENCES films (id) ON DELETE CASCADE, \n\tFOREIGN KEY(genre_id) REFERENCES genres (id) ON DELETE RESTRICT\n)\n\n')
    op.execute('\nCREATE TABLE schedule_bindings (\n\tid VARCHAR(36) NOT NULL, \n\tfilm_id INTEGER NOT NULL, \n\tformat_id INTEGER NOT NULL, \n\tshow_date DATE NOT NULL, \n\tstart_time TIME WITHOUT TIME ZONE NOT NULL, \n\tend_time TIME WITHOUT TIME ZONE NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\tfilm_version INTEGER NOT NULL, \n\tfilm_snapshot JSON NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(film_id, format_id) REFERENCES film_formats (film_id, format_id) ON DELETE RESTRICT\n)\n\n')
    op.execute('CREATE INDEX ix_schedule_bindings_film_id ON schedule_bindings (film_id)')


def downgrade():
    op.drop_table('schedule_bindings')
    op.drop_table('film_genres')
    op.drop_table('film_formats')
    op.drop_table('combo_items')
    op.drop_table('genres')
    op.drop_table('formats')
    op.drop_table('food_quotes')
    op.drop_table('food_items')
    op.drop_table('films')
