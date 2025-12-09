import click
from loguru import logger

from dbpromotions.populate import populate_database, refresh_levels


@click.command()
@click.option("-r", "--refresh", is_flag=True, default=False)
@click.option("-m", "--max-to-update", type=int, default=50)
def main(refresh: bool = False, max_to_update: int = 50) -> None:
    if refresh:
        logger.info("Refreshing levels.")
        refresh_levels()
    else:
        logger.info("Updating the DB.")
        populate_database(max_to_update=max_to_update)


if __name__ == "__main__":
    main()
