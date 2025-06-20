import re
from datetime import UTC, datetime, timedelta
from itertools import batched

import peewee
from danbooru.models.post_counts import DanbooruPostCounts
from danbooru.models.post_version import DanbooruPostVersion
from danbooru.models.user import DanbooruUser
from danbooru.reports.post_appeal_report import DanbooruPostAppealReport
from danbooru.reports.post_report import DanbooruPostReport
from danbooru.user_level import UserLevel
from loguru import logger
from pydantic import BaseModel, computed_field, field_validator

from dbpromotions import Defaults
from dbpromotions.database import PromotionCandidate, init_database


class IncompleteUserData(BaseModel):
    id: int | None = None
    name: str
    level: UserLevel | None = None
    created_at: datetime | None = None

    last_checked: datetime | None = None

    is_banned: bool | None = None

    total_posts: int | None = None
    total_deleted_posts: int | None = None

    recent_posts: int | None = None
    recent_deleted_posts: int | None = None

    post_edits: int | None = None

    last_edit: datetime | None = None

    total_note_edits: int | None = None
    # recent_note_edits: int | None = None

    # total_wiki_edits: int | None = None
    # recent_wiki_edits: int | None = None

    # total_artist_edits: int | None = None
    # recent_artist_edits: int | None = None

    # total_appeals: int | None = None
    # recent_appeals: int | None = None

    # total_forum_posts: int | None = None
    # recent_forum_posts: int | None = None

    def save_to_db(self, update: bool = False) -> bool:
        try:
            user = PromotionCandidate.get(self.id)
        except peewee.DoesNotExist:
            user = PromotionCandidate(id=self.id)
            self.last_checked = None
        else:
            self.last_checked = user.last_checked

        fetched = False
        if self.last_checked and self.last_checked > (datetime.now() - timedelta(days=5)):  # noqa: DTZ005
            logger.info(f"User {self.id} was already checked recently.")
        elif update:
            self.last_checked = datetime.now(tz=UTC)
            logger.info(f"Populating missing values for user {self.id}.")
            self.populate_other_values()
            fetched = True
        else:
            logger.info("Reached the limit for fetchable user info in the current session. Skipping until next scan.")

        user_data = self.model_dump(exclude_none=True)
        for key, value in user_data.items():
            setattr(user, key, value)

        user.save()
        return fetched

    @classmethod
    def update_from_danbooru_user(cls, user: DanbooruUser) -> None:
        db_user = PromotionCandidate.get(user.id)
        user_data = IncompleteUserData.from_danbooru_user(user)
        for key, value in user_data.model_dump(exclude_none=True).items():
            setattr(db_user, key, value)
        db_user.save()

    def populate_other_values(self) -> None:
        if self.total_posts == 0:
            self.recent_posts = 0
            self.total_deleted_posts = 0
        else:
            count_search = DanbooruPostCounts.get(tags=f"user:{self.name} date:{Defaults.RECENT_SINCE_STR}..",
                                                  cache=True)  # type: ignore[var-annotated] # one fucking job
            self.recent_posts = count_search.count

            count_search = DanbooruPostCounts.get(tags=f"status:deleted user:{self.name}",
                                                  cache=True)  # type: ignore[var-annotated] # one fucking job
            self.total_deleted_posts = count_search.count  # type: ignore[attr-defined]

            if self.recent_posts == 0:
                self.recent_deleted_posts = 0
            else:
                count_search = DanbooruPostCounts.get(
                    tags=f"status:deleted user:{self.name} date:{Defaults.RECENT_SINCE_STR}..",
                    cache=True,
                )  # type: ignore[var-annotated] # one fucking job
                self.recent_deleted_posts = count_search.count      # type: ignore[attr-defined]

        last_version, = DanbooruPostVersion.get(updater_id=self.id, cache=True, limit=1)
        self.last_edit = last_version.updated_at

    @field_validator("name", mode="after")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return value.replace(" ", "_")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_deleted(self) -> bool:
        return bool(re.match(r"^user_\d+$", self.name))

    @staticmethod
    def from_danbooru_user(user: DanbooruUser) -> "IncompleteUserData":
        data = user.model_dump(exclude_none=True)
        extra_data = {
            "total_posts": user.post_upload_count,  # type: ignore[attr-defined]
            "total_note_edits": user.note_update_count,  # type: ignore[attr-defined]
            "post_edits": user.post_update_count,  # type: ignore[attr-defined]
            "level": user.level_string,  # type: ignore[attr-defined]
        }
        return IncompleteUserData(**data | extra_data)


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
    recent_uploader_data = DanbooruPostReport.get(**params)  # type: ignore[arg-type]
    return [IncompleteUserData(name=r.uploader, recent_posts=r.posts, recently_active=True) for r in recent_uploader_data]


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
    recent_uploader_data = DanbooruPostReport.get(**params)  # type: ignore[arg-type]
    return [IncompleteUserData(name=r.uploader, recent_deleted_posts=r.posts, recently_active=True) for r in recent_uploader_data]


def get_non_contributor_uploaders_deleted() -> list[IncompleteUserData]:
    params = {
        "from": "2005-05-23",
        "to": Defaults.RECENT_UNTIL_STR,
        "group": "uploader",
        "group_limit": 1000,
        "uploader": {
            "level": "<35",
        },
        "tags": "status:deleted",
    }
    uploader_data = DanbooruPostReport.get(**params)  # type: ignore[arg-type]
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


# def get_biggest_non_builder_wiki_editors() -> list[IncompleteUserData]:
#     params = {
#         "group": "updater",
#         "group_limit": 1000,
#         "updater": {
#             "level": "<32",
#         },
#     }
#
#     recent_uploader_data = DanbooruWikiPageVersionReport.get(**params)
#     return [IncompleteUserData(name=r.updater, wiki_edits=r.wiki_edits) for r in recent_uploader_data]
#
#
# def get_biggest_non_builder_artist_editors() -> list[IncompleteUserData]:
#     params = {
#         "group": "updater",
#         "group_limit": 1000,
#         "updater": {
#             "level": "<32",
#         },
#     }
#
#     recent_uploader_data = DanbooruArtistVersionReport.get(**params)
#     return [IncompleteUserData(name=r.updater, artist_edits=r.artist_edits) for r in recent_uploader_data]
#
#
# def get_biggest_non_builder_forum_posters() -> list[IncompleteUserData]:
#     params = {
#         "group": "creator",
#         "group_limit": 1000,
#         "updater": {
#             "level": "<32",
#         },
#     }
#
#     recent_uploader_data = DanbooruForumPostReport.get(**params)
#     return [IncompleteUserData(name=r.creator, artist_edits=r.forum_posts) for r in recent_uploader_data]


def get_biggest_non_builder_appealers() -> list[IncompleteUserData]:
    params = {
        "group": "creator",
        "group_limit": 1000,
        "updater": {
            "level": "<32",
        },
    }

    recent_uploader_data = DanbooruPostAppealReport.get(**params)  # type: ignore[arg-type]
    return [IncompleteUserData(name=r.creator, artist_edits=r.appeals) for r in recent_uploader_data]


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

    logger.info("Fetching recent uploaders...")
    merge_map(user_map_by_name, get_recent_non_contributor_uploaders(), add_missing=False)

    logger.info("Fetching deleted posts...")
    merge_map(user_map_by_name, get_non_contributor_uploaders_deleted(), add_missing=False)

    logger.info("Fetching recent deleted posts...")
    merge_map(user_map_by_name, get_recent_non_contributor_uploaders_deleted(), add_missing=False)

    # TODO: the following won't work because they're only recent, but I want historical data. IDK how to get it.
    # Maybe bigquery? or just individual user fetching.
    # or just get both total and latest

    # logger.info("Fetching biggest wiki editors...")
    # merge_map(incomplete_map_by_name, get_biggest_non_builder_wiki_editors())

    # logger.info("Fetching biggest artist editors...")
    # merge_map(incomplete_map_by_name, get_biggest_non_builder_artist_editors())

    # logger.info("Fetching biggest forum posters...")
    # merge_map(incomplete_map_by_name, get_biggest_non_builder_forum_posters())

    # logger.info("Fetching biggest appealers...")
    # merge_map(incomplete_map_by_name, get_biggest_non_builder_appealers())

    return user_map_by_name


def seed_missing_data(user_map_by_name: dict[str, IncompleteUserData], max_to_update: int) -> dict[int, IncompleteUserData]:
    user_map_by_id: dict[int, IncompleteUserData] = {}
    missing_ids: list[IncompleteUserData] = []

    processed = 0
    fetched = 0

    for user_data in user_map_by_name.values():
        if user_data.id:
            fetched += user_data.save_to_db(update=fetched < max_to_update)
            processed += 1
            logger.info(f"At user {processed} of {len(user_map_by_name)}")
            user_map_by_id[user_data.id] = user_data
        else:
            missing_ids.append(user_data)

    for missing_id in missing_ids:
        user, = DanbooruUser.get(**{"search[name]": missing_id.name})  # type: ignore[arg-type]
        user_data = IncompleteUserData(**user.model_dump(exclude_none=True))
        fetched += user_data.save_to_db(update=fetched < max_to_update)
        processed += 1
        logger.info(f"At user {processed} of {len(user_map_by_name)}")
        user_map_by_id[user.id] = user_data

    return user_map_by_id


def populate_database() -> None:
    init_database()
    user_map_by_name = get_user_map_by_name()
    logger.info(f"Processing {len(user_map_by_name)} users.")
    seed_missing_data(user_map_by_name, max_to_update=50)


def get_known_user_ids() -> set[int]:
    known_users = PromotionCandidate.select(PromotionCandidate.id).dicts()
    return {u["id"] for u in known_users}


def refresh_levels() -> None:
    user_ids = get_known_user_ids()
    for user_batch in batched(user_ids, 100):
        updated_users = DanbooruUser.get_all(id=",".join(map(str, user_batch)))
        for user in updated_users:
            IncompleteUserData.update_from_danbooru_user(user)


if __name__ == "__main__":
    populate_database()
