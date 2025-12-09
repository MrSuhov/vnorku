"""
Database cleanup utilities - kill stuck transactions before starting work
"""
import asyncio
from sqlalchemy import text
from shared.database.connection import async_engine
from shared.utils.unified_logging import get_logger

logger = get_logger(__name__)


async def kill_stuck_transactions(
    idle_threshold_seconds: int = 300,  # 5 минут
    exclude_apps: list = None
) -> int:
    """
    Убивает зависшие транзакции в состоянии 'idle in transaction'

    Args:
        idle_threshold_seconds: Порог времени бездействия в секундах
        exclude_apps: Список application_name для исключения (например, ['pgAdmin'])

    Returns:
        Количество убитых транзакций
    """
    if exclude_apps is None:
        exclude_apps = ['pgAdmin', 'psql']

    logger.info(f"🔍 Checking for stuck transactions (idle > {idle_threshold_seconds}s)...")

    # Формируем условие исключения приложений
    exclude_condition = " AND ".join([f"application_name NOT LIKE '%{app}%'" for app in exclude_apps])
    if not exclude_condition:
        exclude_condition = "1=1"

    query = f"""
    SELECT
        pid,
        application_name,
        state,
        query_start,
        state_change,
        NOW() - state_change AS idle_duration,
        LEFT(query, 100) as query_preview
    FROM pg_stat_activity
    WHERE
        datname = 'korzinka'
        AND state = 'idle in transaction'
        AND {exclude_condition}
        AND (NOW() - state_change) > INTERVAL '{idle_threshold_seconds} seconds'
    ORDER BY state_change ASC;
    """

    killed_count = 0

    async with async_engine.connect() as conn:
        # Получаем список зависших транзакций
        result = await conn.execute(text(query))
        stuck_transactions = result.fetchall()

        if not stuck_transactions:
            logger.info("✅ No stuck transactions found")
            return 0

        logger.warning(f"⚠️ Found {len(stuck_transactions)} stuck transaction(s):")

        for row in stuck_transactions:
            pid = row[0]
            app_name = row[1] or "unknown"
            state = row[2]
            query_start = row[3]
            state_change = row[4]
            idle_duration = row[5]
            query_preview = row[6] or "N/A"

            logger.warning(
                f"  PID {pid}: {app_name} | "
                f"State: {state} | "
                f"Idle: {idle_duration} | "
                f"Query: {query_preview[:50]}..."
            )

            # Убиваем транзакцию
            try:
                kill_result = await conn.execute(
                    text("SELECT pg_terminate_backend(:pid)"),
                    {"pid": pid}
                )
                terminated = kill_result.scalar()

                if terminated:
                    logger.info(f"✅ Killed stuck transaction PID {pid}")
                    killed_count += 1
                else:
                    logger.error(f"❌ Failed to kill PID {pid}")
            except Exception as e:
                logger.error(f"❌ Error killing PID {pid}: {e}")

        await conn.commit()

    if killed_count > 0:
        logger.info(f"✅ Killed {killed_count} stuck transaction(s)")

    return killed_count


async def get_active_connections_info() -> dict:
    """
    Получает информацию о всех активных подключениях к базе

    Returns:
        Словарь с статистикой по application_name
    """
    query = """
    SELECT
        COALESCE(application_name, 'unknown') as app_name,
        state,
        COUNT(*) as count
    FROM pg_stat_activity
    WHERE datname = 'korzinka'
    GROUP BY app_name, state
    ORDER BY count DESC;
    """

    async with async_engine.connect() as conn:
        result = await conn.execute(text(query))
        rows = result.fetchall()

        connections = {}
        for row in rows:
            app_name, state, count = row
            if app_name not in connections:
                connections[app_name] = {}
            connections[app_name][state] = count

        return connections


async def log_connection_stats():
    """Логирует текущую статистику подключений"""
    logger.info("📊 Database connection statistics:")

    connections = await get_active_connections_info()

    for app_name, states in connections.items():
        total = sum(states.values())
        logger.info(f"  {app_name}: {total} connection(s)")
        for state, count in states.items():
            logger.info(f"    - {state}: {count}")


async def cleanup_before_start():
    """
    Автоматическая очистка перед началом работы
    Вызывается при старте сервисов
    """
    logger.info("🧹 Starting database cleanup...")

    # Показываем текущую статистику
    await log_connection_stats()

    # Убиваем зависшие транзакции (старше 5 минут)
    killed = await kill_stuck_transactions(
        idle_threshold_seconds=300,
        exclude_apps=['pgAdmin', 'psql']
    )

    if killed > 0:
        logger.info("✅ Database cleanup completed")
        # Показываем обновлённую статистику
        await log_connection_stats()
    else:
        logger.info("✅ Database is clean - no cleanup needed")

    return killed


if __name__ == "__main__":
    # Для ручного запуска
    asyncio.run(cleanup_before_start())
