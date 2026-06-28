"""内置定时调度 — 程序内部闭环，不依赖外部 crontab"""

import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger("stockData.scheduler")
scheduler = BackgroundScheduler(timezone="Asia/Shanghai")


def _run_task(name: str, cli_mode: str):
    """执行采集任务（在线程中运行）"""
    import sys
    from collector import collect_snapshots, collect_sectors

    logger.info(f"🕐 [{name}] 开始采集...")
    t0 = datetime.now()

    try:
        if cli_mode == "--snapshot":
            stats = collect_snapshots(verbose=False)
            msg = f"估值快照: {stats['snapshot']} 条"
        elif cli_mode == "--sector":
            stats = collect_sectors(verbose=False)
            msg = f"行业 {stats['industry']} + 概念 {stats['concept']} = {stats['industry']+stats['concept']} 条 | 清理 {stats['cleaned']} | 缺 {stats.get('missing_days',0)} 天"
        elif cli_mode == "--a":
            from collector import collect_all, TARGET_COMPANIES
            targets = [t for t in TARGET_COMPANIES if t["exchange"] != "HK"]
            stats = collect_all(targets=targets, verbose=False)
            msg = f"A股: {stats['summary']} 条财务摘要 + {stats['indicators']} 条指标"
        elif cli_mode == "--hk":
            from collector import collect_all, TARGET_COMPANIES
            targets = [t for t in TARGET_COMPANIES if t["exchange"] == "HK"]
            stats = collect_all(targets=targets, verbose=False)
            msg = f"港股: {stats['summary']} 条财务摘要 + {stats['indicators']} 条指标"
        else:
            msg = f"未知模式: {cli_mode}"

        elapsed = (datetime.now() - t0).total_seconds()
        logger.info(f"✅ [{name}] {msg}（耗时 {elapsed:.1f}s）")

    except Exception as e:
        logger.error(f"❌ [{name}] 采集失败: {e}")


def init_scheduler():
    """注册定时任务（每天非交易日跳过）"""
    logger.info("🕐 初始化内置定时调度...")

    # 估值快照 - 交易日 03:00
    scheduler.add_job(
        _run_task,
        CronTrigger(day_of_week="mon-fri", hour=3, minute=0),
        args=["估值快照", "--snapshot"],
        id="stockdata_snapshot",
        replace_existing=True,
        misfire_grace_time=600,
    )

    # A股基本面 - 交易日 15:30
    scheduler.add_job(
        _run_task,
        CronTrigger(day_of_week="mon-fri", hour=15, minute=30),
        args=["A股基本面", "--a"],
        id="stockdata_ashare",
        replace_existing=True,
        misfire_grace_time=600,
    )

    # 板块数据 - 交易日 16:00
    scheduler.add_job(
        _run_task,
        CronTrigger(day_of_week="mon-fri", hour=16, minute=0),
        args=["板块数据", "--sector"],
        id="stockdata_sectors",
        replace_existing=True,
        misfire_grace_time=600,
    )

    # 港股基本面 - 交易日 16:30
    scheduler.add_job(
        _run_task,
        CronTrigger(day_of_week="mon-fri", hour=16, minute=30),
        args=["港股基本面", "--hk"],
        id="stockdata_hk",
        replace_existing=True,
        misfire_grace_time=600,
    )

    scheduler.start()
    logger.info("✅ 内置定时调度已启动")

    # 打印当前注册的任务
    for job in scheduler.get_jobs():
        logger.info(f"  📅 {job.id}: {job.trigger}")


def stop_scheduler():
    """关闭调度器"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("⏹ 内置定时调度已关闭")


# 任务状态 API
def get_scheduler_status() -> dict:
    """获取调度器状态"""
    return {
        "running": scheduler.running,
        "jobs": [
            {
                "id": j.id,
                "next_run": str(j.next_run_time) if j.next_run_time else None,
                "trigger": str(j.trigger),
            }
            for j in scheduler.get_jobs()
        ],
    }
