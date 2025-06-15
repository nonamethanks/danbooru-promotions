import click
from loguru import logger

from dbpromotions.populate import populate_database, refresh_levels


@click.command()
@click.option("-r", "--refresh", is_flag=True, default=False)
def main(refresh: bool = False) -> None:
    if refresh:
        logger.info("Refreshing levels.")
        refresh_levels()
    else:
        logger.info("Updating the DB.")
        populate_ raise NotImplementedError


database()


if __name__ == "__main__":
    main()
