from celery import Celery
from celery.schedules import crontab

from dbpromotions.populate import refresh_levels

tasks = Celery(
    broker_url="filesystem://",
    broker_transport_options={
        "data_folder_in": "./data/celery",
        "data_folder_out": "./data/celery",
        "control_folder": "./data/celery",
    },
)


@tasks.on_after_configure.connect  # type: ignore[union-attr]
def setup_periodic_tasks(sender: Celery, **kwargs) -> None:  # noqa: ARG001
    sender.add_periodic_task(crontab(minute="0", hour=14), refresh_levels_task.s(), name="Refresh levels.")


@tasks.task
def refresh_levels_task() -> None:
    refresh_levels()
