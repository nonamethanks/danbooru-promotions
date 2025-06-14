import re
from datetime import UTC, datetime

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

    is_banned: bool | None = None

    total_posts: int | None = None
    total_deleted_posts: int | None = None

    recent_posts: int | None = None
    recent_deleted_posts: int | None = None

    post_edits: int | None = None
    last_edit_at: datetime | None = None

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

    def save_to_db(self) -> None:
        self.seed_null_values()
        user = PromotionCandidate(**self.model_dump(exclude_none=True))
        user.save()

    def seed_null_values(self) -> None:
        if self.total_deleted_posts is None:
            count_search = DanbooruPostCounts.get(tags=f"status:deleted user:{self.name}",
                                                  cache=True)  # type: ignore[var-annotated] # one fucking job
            self.total_deleted_posts = count_search.count

        if self.recent_deleted_posts is None:
            count_search = DanbooruPostCounts.get(
                tags=f"status:deleted user:{self.name} date:{Defaults.RECENT_SINCE_STR}..",
                cache=True,
            )  # type: ignore[var-annotated] # one fucking job
            self.total_deleted_posts = count_search.count      # type: ignore[attr-defined]

        if self.last_edit_at is None:
            last_version, = DanbooruPostVersion.get(updater_id=self.id, cache=True, limit=1)
            self.last_edit_at = last_version.updated_at

    @field_validator("name", mode="after")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return value.replace(" ", "_")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def last_checked(self) -> datetime:
        return datetime.now(tz=UTC)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_deleted(self) -> bool:
        return bool(re.match(r"user_\d+", self.name))

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
    recent_uploader_data = DanbooruPostReport.get(**params)
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
    recent_uploader_data = DanbooruPostReport.get(**params)
    return [IncompleteUserData(name=r.uploader, recent_deleted_posts=r.posts) for r in recent_uploader_data]


def get_non_contributor_uploaders() -> list[IncompleteUserData]:
    users = DanbooruUser.get_all(
        post_upload_count=">10",
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

    recent_uploader_data = DanbooruPostAppealReport.get(**params)
    return [IncompleteUserData(name=r.creator, artist_edits=r.appeals) for r in recent_uploader_data]


def merge_map(user_map: dict[str, IncompleteUserData], user_data: list[IncompleteUserData]) -> None:
    for new_user_data in user_data:
        old_user_data = user_map.get(new_user_data.name)
        if not old_user_data:
            user_map[new_user_data.name] = new_user_data
            continue

        new_data = old_user_data.model_dump(exclude_none=True) | new_user_data.model_dump(exclude_none=True)
        user_map[old_user_data.name] = IncompleteUserData(**new_data)


def get_known_users() -> dict[int, IncompleteUserData]:
    known_users = PromotionCandidate.select().dicts()
    known_user_data = {u["id"]: IncompleteUserData(**u) for u in known_users}
    return known_user_data


def get_user_map_by_name() -> dict[str, IncompleteUserData]:
    user_map_by_name: dict[str, IncompleteUserData] = {}

    logger.info("Fetching recent uploaders...")
    merge_map(user_map_by_name, get_recent_non_contributor_uploaders())

    logger.info("Fetching recent deleted posts...")
    merge_map(user_map_by_name, get_recent_non_contributor_uploaders_deleted())

    logger.info("Fetching biggest gardeners...")
    merge_map(user_map_by_name, get_biggest_non_builder_gardeners())

    logger.info("Fetching biggest translators...")
    merge_map(user_map_by_name, get_biggest_non_builder_translators())

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

    logger.info("Fetching biggest non-contrib uploaders...")
    for uploader_data in get_non_contributor_uploaders():
        old_user_data = user_map_by_name.get(uploader_data.name)
        if not old_user_data:
            assert uploader_data.total_posts
            if uploader_data.total_posts > Defaults.MIN_UPLOADS:
                user_map_by_name[uploader_data.name] = uploader_data
            continue

        new_data = old_user_data.model_dump(exclude_none=True) | uploader_data.model_dump(exclude_none=True)
        user_map_by_name[old_user_data.name] = IncompleteUserData(**new_data)

    return user_map_by_name


def seed_ids(user_map_by_name: dict[str, IncompleteUserData]) -> dict[int, IncompleteUserData]:
    user_map_by_id: dict[int, IncompleteUserData] = {}
    missing_ids: list[IncompleteUserData] = []

    for user_data in user_map_by_name.values():
        if user_data.id:
            user_data.save_to_db()
            user_map_by_id[user_data.id] = user_data
        else:
            missing_ids.append(user_data)

    for index, missing_id in enumerate(missing_ids):
        logger.info(f"Fetching ID for user {missing_id.name}, {index+1}/{len(missing_ids)}")
        user, = DanbooruUser.get(**{"search[name]": missing_id.name})
        user_data = IncompleteUserData(**user.model_dump(exclude_none=True))
        user_data.save_to_db()
        user_map_by_id[user.id] = user_data

    return user_map_by_id


def populate_database() -> None:
    init_database()
    user_map_by_name = get_user_map_by_name()
    logger.info(f"Processing {len(user_map_by_name)} users.")
    user_map_by_id = seed_ids(user_map_by_name)


if __name__ == "__main__":
    populate_database()
