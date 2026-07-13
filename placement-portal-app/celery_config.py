from datetime import timedelta

broker_url = "redis://localhost:6379/0"
result_backend = "redis://localhost:6379/0"
timezone = "Asia/Kolkata"
enable_utc = True

beat_schedule = {
    "interview-reminder-test-every-minute": {
        "task": "application.tasks.interview_reminder",
        "schedule": timedelta(minutes=1),
    },
    "deadline-reminder-test-every-minute": {
        "task": "application.tasks.deadline_reminder",
        "schedule": timedelta(minutes=1),
    },
    "monthly-placement-report-test-every-minute": {
        "task": "application.tasks.monthly_placement_report",
        "schedule": timedelta(minutes=1),
    },
}