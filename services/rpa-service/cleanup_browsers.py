#!/usr/bin/env python3
"""
Утилита для очистки зависших chromedriver и Chrome процессов.
Вызывается автоматически при старте RPA сервиса.
"""

import subprocess
import logging
import psutil
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def kill_orphaned_chromedrivers(max_age_hours: int = 1):
    """
    Убивает chromedriver процессы старше указанного времени

    Args:
        max_age_hours: Максимальный возраст процесса в часах (по умолчанию 1 час)
    """
    killed_count = 0
    current_time = datetime.now()

    try:
        for proc in psutil.process_iter(['pid', 'name', 'create_time', 'cmdline']):
            try:
                # Проверяем chromedriver процессы
                if 'chromedriver' in proc.info['name'].lower():
                    process_age = current_time - datetime.fromtimestamp(proc.info['create_time'])

                    if process_age > timedelta(hours=max_age_hours):
                        logger.warning(
                            f"🧹 Killing orphaned chromedriver PID={proc.info['pid']} "
                            f"(age: {process_age.total_seconds()/3600:.1f}h)"
                        )
                        proc.kill()
                        killed_count += 1
                    else:
                        logger.debug(
                            f"⏳ Keeping recent chromedriver PID={proc.info['pid']} "
                            f"(age: {process_age.total_seconds()/60:.1f}m)"
                        )

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

    except Exception as e:
        logger.error(f"❌ Error scanning processes: {e}")

    if killed_count > 0:
        logger.info(f"✅ Cleaned up {killed_count} orphaned chromedriver processes")
    else:
        logger.info("✅ No orphaned chromedriver processes found")

    return killed_count


def kill_orphaned_chrome_browsers(max_age_hours: int = 1):
    """
    Убивает Chrome процессы старше указанного времени (только те, что запущены из automation)

    Args:
        max_age_hours: Максимальный возраст процесса в часах
    """
    killed_count = 0
    current_time = datetime.now()

    try:
        for proc in psutil.process_iter(['pid', 'name', 'create_time', 'cmdline']):
            try:
                # Проверяем Chrome процессы
                if 'chrome' in proc.info['name'].lower() or 'chromium' in proc.info['name'].lower():
                    cmdline = proc.info.get('cmdline', [])

                    # Убиваем только automation Chrome (с --remote-debugging-port или --user-data-dir)
                    is_automation_chrome = any(
                        '--remote-debugging-port' in arg or
                        '--user-data-dir' in arg or
                        '--enable-automation' in arg
                        for arg in cmdline if arg
                    )

                    if is_automation_chrome:
                        process_age = current_time - datetime.fromtimestamp(proc.info['create_time'])

                        if process_age > timedelta(hours=max_age_hours):
                            logger.warning(
                                f"🧹 Killing orphaned Chrome PID={proc.info['pid']} "
                                f"(age: {process_age.total_seconds()/3600:.1f}h)"
                            )
                            proc.kill()
                            killed_count += 1

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

    except Exception as e:
        logger.error(f"❌ Error scanning Chrome processes: {e}")

    if killed_count > 0:
        logger.info(f"✅ Cleaned up {killed_count} orphaned Chrome processes")
    else:
        logger.info("✅ No orphaned Chrome processes found")

    return killed_count


def cleanup_all_browsers(max_age_hours: int = 1):
    """
    Полная очистка всех зависших браузерных процессов

    Args:
        max_age_hours: Максимальный возраст процесса в часах
    """
    logger.info("🧹 Starting browser cleanup...")

    chromedriver_count = kill_orphaned_chromedrivers(max_age_hours)
    chrome_count = kill_orphaned_chrome_browsers(max_age_hours)

    total_killed = chromedriver_count + chrome_count

    if total_killed > 0:
        logger.info(f"✅ Cleanup completed: killed {total_killed} processes")
    else:
        logger.info("✅ Cleanup completed: no orphaned processes found")

    return total_killed


def emergency_kill_all():
    """
    Аварийное завершение ВСЕХ chromedriver и Chrome процессов
    Использовать только для критических ситуаций
    """
    logger.warning("⚠️ EMERGENCY CLEANUP: Killing ALL chromedriver and Chrome processes!")

    killed_count = 0

    try:
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                name = proc.info['name'].lower()
                if 'chromedriver' in name or 'chrome' in name or 'chromium' in name:
                    logger.warning(f"🧹 Force killing {proc.info['name']} PID={proc.info['pid']}")
                    proc.kill()
                    killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception as e:
        logger.error(f"❌ Error in emergency cleanup: {e}")

    logger.warning(f"⚠️ Emergency cleanup completed: killed {killed_count} processes")
    return killed_count


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Аргументы командной строки
    if len(sys.argv) > 1:
        if sys.argv[1] == "--emergency":
            emergency_kill_all()
        elif sys.argv[1] == "--max-age":
            max_age = int(sys.argv[2]) if len(sys.argv) > 2 else 1
            cleanup_all_browsers(max_age_hours=max_age)
        else:
            print("Usage:")
            print("  python cleanup_browsers.py                    # Normal cleanup (1h old)")
            print("  python cleanup_browsers.py --max-age 2        # Cleanup processes older than 2h")
            print("  python cleanup_browsers.py --emergency        # Kill ALL browser processes")
    else:
        # По умолчанию: очистка процессов старше 1 часа
        cleanup_all_browsers(max_age_hours=1)
