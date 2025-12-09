"""Add updated_at fields and triggers

Revision ID: f66951acb50f
Revises: 20250918_user_sessions_lsd_account_id
Create Date: 2025-09-18 11:00:04.432871

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f66951acb50f'
down_revision = '20250918_user_sessions_lsd_account_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Список таблиц, в которые нужно добавить updated_at (если его нет)
    tables_to_add_updated_at = [
        'lsd_accounts',
        'promotions', 
        'product_prices',
        'basket_analyses',
        'user_sessions'
    ]
    
    # Добавляем поле updated_at в таблицы, где его нет
    for table in tables_to_add_updated_at:
        # Проверяем, есть ли уже поле updated_at
        conn = op.get_bind()
        result = conn.execute(sa.text(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = '{table}' AND column_name = 'updated_at'
        """))
        
        if not result.fetchone():
            # Добавляем поле updated_at
            op.add_column(table, sa.Column('updated_at', sa.DateTime(timezone=True), 
                                         server_default=sa.func.now(), 
                                         onupdate=sa.func.now()))
            print(f"Added updated_at to {table}")
        else:
            print(f"updated_at already exists in {table}")
    
    # Создаем функцию для автоматического обновления updated_at
    conn = op.get_bind()
    conn.execute(sa.text("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $ language 'plpgsql';
    """))
    
    # Список всех таблиц, для которых нужны триггеры
    all_tables = [
        'users',
        'orders', 
        'lsd_configs',
        'lsd_accounts',
        'promotions',
        'product_prices',
        'basket_analyses',
        'user_sessions'
    ]
    
    # Создаем триггеры для всех таблиц
    for table in all_tables:
        trigger_name = f"update_{table}_updated_at"
        
        # Удаляем триггер если уже существует
        conn.execute(sa.text(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table};"))
        
        # Создаем новый триггер
        conn.execute(sa.text(f"""
            CREATE TRIGGER {trigger_name}
                BEFORE UPDATE ON {table}
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();
        """))
        
        print(f"Created trigger {trigger_name}")


def downgrade() -> None:
    # Список всех таблиц
    all_tables = [
        'users',
        'orders', 
        'lsd_configs',
        'lsd_accounts',
        'promotions',
        'product_prices',
        'basket_analyses',
        'user_sessions'
    ]
    
    conn = op.get_bind()
    
    # Удаляем все триггеры
    for table in all_tables:
        trigger_name = f"update_{table}_updated_at"
        conn.execute(sa.text(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table};"))
        print(f"Dropped trigger {trigger_name}")
    
    # Удаляем функцию
    conn.execute(sa.text("DROP FUNCTION IF EXISTS update_updated_at_column();"))
    
    # Мы не удаляем поля updated_at, так как они могут содержать полезные данные
    # Если надо будет удалить, можно добавить:
    # op.drop_column('table_name', 'updated_at')
