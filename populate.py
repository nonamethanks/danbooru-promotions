import click
from loguru import logger

from dbpromotions.populate import populate_database, refresh_levels


@click.command()
@click.option("-r", "--refresh", is_flag=True, default=False)
@click.option("-m", "--max-to-update", type=int, default=50)
@click.option("-n", "--resume-from", type=int, default=0)
def main(refresh: bool = False, max_to_update: int = 50, resume_from: int = 0) -> None:
    if refresh:
        logger.info("Refreshing levels.")
        refresh_levels()
    else:
        logger.info("Updating the DB.")
        populate_database(max_to_update=max_to_update, resume_from=resume_from)


if __name__ == "__main__":
    main()
