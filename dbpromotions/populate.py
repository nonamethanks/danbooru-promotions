from itertools import batched

from danbooru.models import DanbooruUser
from danbooru.reports import (
    DanbooruArtistVersionReport,
    DanbooruForumPostReport,
    DanbooruPostReport,
    DanbooruWikiPageVersionReport,
)
from loguru import logger

from dbpromotions import Defaults
from dbpromotions.database import PromotionCandidate, PromotionCandidateEdits, init_database
from dbpromotions.incomplete_user_data import IncompleteUserData


def get_recent_non_contributor_uploaders() -> list[IncompleteUserData]:
    params = {
        "from": Defaults.RECENT_SINCE_STR,
        "to": Defaults.RECENT_UNTIL_STR,
        "group": "uploader",
        "group_limit": 1000,
        "uploader": {
            "level": "<35",
        },
    }
    recent_uploader_data = DanbooruPostReport.get(**params, cache=True)  # type: ignore[arg-type]
    return [IncompleteUserData(name=r.uploader, recent_posts=r.posts) for r in recent_uploader_data]


def get_recent_non_contributor_uploaders_deleted() -> list[IncompleteUserData]:
    params = {
        "from": Defaults.RECENT_SINCE_STR,
        "to": Defaults.RECENT_UNTIL_STR,
        "group": "uploader",
        "group_limit": 1000,
        "uploader": {
            "level": "<35",
        },
        "tags": "status:deleted",
    }
    recent_uploader_data = DanbooruPostReport.get(**params, cache=True)  # type: ignore[arg-type]
    return [IncompleteUserData(name=r.uploader, recent_deleted_posts=r.posts) for r in recent_uploader_data]


def get_non_contributor_uploaders_deleted() -> list[IncompleteUserData]:
    params = {
        "from": Defaults.DANBOORU_START_DATE_STR,
        "to": Defaults.RECENT_UNTIL_STR,
        "group": "uploader",
        "group_limit": 1000,
        "uploader": {
            "level": "<35",
        },
        "tags": "status:deleted",
    }
    uploader_data = DanbooruPostReport.get(**params, cache=True)  # type: ignore[arg-type]
    return [IncompleteUserData(name=r.uploader, total_deleted_posts=r.posts) for r in uploader_data]


def get_non_contributor_uploaders() -> list[IncompleteUserData]:
    users = DanbooruUser.get_all(
        post_upload_count=f">{Defaults.MIN_UPLOADS}",
        order="post_upload_count",
        level="<35",
    )

    return [IncompleteUserData.from_danbooru_user(u) for u in users]


def get_biggest_non_builder_gardeners() -> list[IncompleteUserData]:
    users = DanbooruUser.get_all(
        order="post_update_count",
        post_update_count=f">{Defaults.MIN_EDITS}",
        level="<32",
    )

    return [IncompleteUserData.from_danbooru_user(u) for u in users]


def get_biggest_non_builder_translators() -> list[IncompleteUserData]:
    users = DanbooruUser.get_all(
        order="note_update_count",
        note_update_count=f">{Defaults.MIN_NOTES}",
        level="<32",
    )

    return [IncompleteUserData.from_danbooru_user(u) for u in users]


def get_biggest_non_builder_wiki_editors() -> list[IncompleteUserData]:
    params = {
        "from": Defaults.DANBOORU_START_DATE_STR,
        "to": Defaults.RECENT_UNTIL_STR,
        "group": "updater",
        "group_limit": 1000,
        "updater": {
            "level": "<32",
        },
    }

    wiki_editor_data = DanbooruWikiPageVersionReport.get(**params, cache=True)
    return [IncompleteUserData(name=r.updater, total_wiki_edits=r.wiki_edits)for r in wiki_editor_data]


def get_biggest_non_builder_artist_editors() -> list[IncompleteUserData]:
    params = {
        "from": Defaults.DANBOORU_START_DATE_STR,
        "to": Defaults.RECENT_UNTIL_STR,
        "group": "updater",
        "group_limit": 1000,
        "updater": {
            "level": "<32",
        },
    }

    artist_editor_data = DanbooruArtistVersionReport.get(**params, cache=True)
    return [IncompleteUserData(name=r.updater, total_artist_edits=r.artist_edits) for r in artist_editor_data]


def get_biggest_non_builder_forum_posters() -> list[IncompleteUserData]:
    params = {
        "from": Defaults.DANBOORU_START_DATE_STR,
        "to": Defaults.RECENT_UNTIL_STR,
        "group": "creator",
        "group_limit": 1000,
        "updater": {
            "level": "<32",
        },
    }
    recent_uploader_data = DanbooruForumPostReport.get(**params, cache=True)
    return [IncompleteUserData(name=r.creator, total_forum_posts=r.forum_posts) for r in recent_uploader_data]


def merge_map(user_map: dict[str, IncompleteUserData], user_data: list[IncompleteUserData], add_missing: bool = True) -> None:
    for new_user_data in user_data:
        old_user_data = user_map.get(new_user_data.name)
        if not old_user_data:
            if add_missing:
                user_map[new_user_data.name] = new_user_data
            continue

        new_data = old_user_data.model_dump(exclude_none=True) | new_user_data.model_dump(exclude_none=True)
        user_map[old_user_data.name] = IncompleteUserData(**new_data)


def get_user_map_by_name() -> dict[str, IncompleteUserData]:
    logger.info("Fetching biggest uploaders...")
    user_map_by_name = {u.name: u for u in get_non_contributor_uploaders()}

    logger.info("Fetching biggest gardeners...")
    merge_map(user_map_by_name, get_biggest_non_builder_gardeners())

    logger.info("Fetching biggest translators...")
    merge_map(user_map_by_name, get_biggest_non_builder_translators())

    logger.info("Fetching biggest wiki editors...")
    editors = get_biggest_non_builder_wiki_editors()
    logger.info("Fetching biggest artist editors...")
    editors += get_biggest_non_builder_artist_editors()
    logger.info("Fetching biggest forum posters...")
    editors += get_biggest_non_builder_forum_posters()

    add_list, merge_list = [], []
    for user in editors:
        if (user.total_wiki_edits or 0) + (user.total_artist_edits or 0) > Defaults.MIN_WIKI_ARTIST_EDITS \
                or (user.total_forum_posts or 0) > Defaults.MIN_FORUM_POSTS:
            add_list.append(user)
        else:
            merge_list.append(user)

    merge_map(user_map_by_name, add_list)
    merge_map(user_map_by_name, merge_list, add_missing=False)

    logger.info("Fetching recent uploaders...")
    merge_map(user_map_by_name, get_recent_non_contributor_uploaders(), add_missing=False)

    logger.info("Fetching deleted posts...")
    merge_map(user_map_by_name, get_non_contributor_uploaders_deleted(), add_missing=False)

    logger.info("Fetching recent deleted posts...")
    merge_map(user_map_by_name, get_recent_non_contributor_uploaders_deleted(), add_missing=False)

    return user_map_by_name


def seed_missing_data(user_map_by_name: dict[str, IncompleteUserData],
                      max_to_update: int,
                      resume_from: int,
                      ) -> dict[int, IncompleteUserData]:
    user_map_by_id: dict[int, IncompleteUserData] = {}
    missing_ids: list[IncompleteUserData] = []

    processed = 0
    fetched = 0
    edit_data_updated = 0

    for user_data in user_map_by_name.values():
        if user_data.id:
            processed += 1
            if processed < resume_from:
                continue

            logger.info(f"At user {processed} of {len(user_map_by_name)}")
            fetched += user_data.save_to_db(update=fetched < max_to_update)
            edit_data_updated += user_data.update_edit_data(update=edit_data_updated < max_to_update)
            user_map_by_id[user_data.id] = user_data
        else:
            missing_ids.append(user_data)

    for missing_id in missing_ids:
        processed += 1

        if processed < resume_from:
            continue

        logger.info(f"At user {processed} of {len(user_map_by_name)}")
        user = DanbooruUser.get_from_name(name=missing_id.name, cache=True)  # type: ignore[call-overload]
        user_data = IncompleteUserData.from_danbooru_user(user)

        fetched += user_data.save_to_db(update=fetched < max_to_update)
        edit_data_updated += user_data.update_edit_data(update=edit_data_updated < max_to_update)
        user_map_by_id[user.id] = user_data

    return user_map_by_id


def populate_database(max_to_update: int = 50, resume_from: int = 0) -> None:
    init_database()
    user_map_by_name = get_user_map_by_name()
    logger.info(f"Processing {len(user_map_by_name)} users.")
    seed_missing_data(user_map_by_name, max_to_update=max_to_update, resume_from=resume_from)


def get_known_user_ids() -> set[int]:
    known_users = PromotionCandidate.select(PromotionCandidate.id).dicts()
    return {u["id"] for u in known_users}


def refresh_levels() -> None:
    user_ids = get_known_user_ids()
    for user_batch in batched(user_ids, 200):
        updated_users = DanbooruUser.get_all(id=",".join(map(str, user_batch)))
        for user in updated_users:
            IncompleteUserData.update_from_danbooru_user(user)


if __name__ == "__main__":
    populate_database()
