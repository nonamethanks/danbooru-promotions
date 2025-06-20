from celery import Celery
from celery.schedules import crontab

from dbpromotions.populate import populate_database, refresh_levels

tasks = Celery(  # type: ignore[call-arg]
    broker_url="filesystem://",
    broker_transport_options={
        "data_folder_in": "./data/celery",
        "data_folder_out": "./data/celery",
        "control_folder": "./data/celery",
    },
)


@tasks.on_after_configure.connect  # type: ignore[union-attr]
def setup_periodic_tasks(sender: Celery, **kwargs) -> None:  # noqa: ARG001
    sender.add_periodic_task(crontab(minute="0", hour="14"), refresh_levels_task.s(), name="Refresh levels.")

    sender.add_periodic_task(crontab(minute="30", hour="*"), populate_database_task.s(), name="Populate database.")


@tasks.task
def refresh_levels_task() -> None:
    refresh_levels()


@tasks.task
def populate_database_task() -> None:
    populate_database()
