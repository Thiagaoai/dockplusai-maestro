from maestro.config import get_settings


def main() -> None:
    settings = get_settings()
    print(
        {
            "status": "dry_run",
            "daily_alert_usd": settings.daily_cost_alert_usd,
            "daily_kill_usd": settings.daily_cost_kill_usd,
            "monthly_kill_usd": settings.monthly_cost_kill_usd,
        }
    )


if __name__ == "__main__":
    main()
