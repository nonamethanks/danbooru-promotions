import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from itertools import batched

import peewee
from danbooru.model import WrongIncludeCallError
from danbooru.models import DanbooruPostCounts, DanbooruPostVersion, DanbooruUser, DanbooruWikiPageVersion
from danbooru.reports import (
    DanbooruArtistVersionReport,
    DanbooruForumPostReport,
    DanbooruPostReport,
    DanbooruWikiPageVersionReport,
)
from danbooru.user_level import UserLevel
from loguru import logger
from pydantic import BaseModel, computed_field, field_validator

from dbpromotions import Defaults
from dbpromotions.database import PromotionCandidate, PromotionCandidateEdits, init_database


class IncompleteUserData(BaseModel):
    id: int | None = None
    name: str
    level: UserLevel | None = None
    created_at: datetime | None = None

    last_checked: datetime | None = None

    is_banned: bool | None = None
    is_deleted: bool | None = None

    total_posts: int | None = None
    total_deleted_posts: int | None = None

    recent_posts: int | None = None
    recent_deleted_posts: int | None = None

    post_edits: int | None = None

    last_edit: datetime | None = None

    total_note_edits: int | None = None
    total_wiki_edits: int | None = None
    total_artist_edits: int | None = None
    total_forum_posts: int | None = None

    low_gentag_posts: int | None = None

    def save_to_db(self, update: bool = False) -> bool:
        try:
            saved_data = PromotionCandidate.get(self.id)
        except peewee.DoesNotExist:
            saved_data = PromotionCandidate(id=self.id)
            self.last_checked = None
            new = True
        else:
            self.last_checked = saved_data.last_checked
            new = False

        if not update and self.last_checked:  # just check anyway if it's a new user
            logger.info("Reached the limit for fetchable user info in the current session. Skipping until next scan.")
        else:
            fetched = self.refresh_user(saved_data)

        self._save(saved_data, new=new)
        return fetched

    def _save(self, saved_data: PromotionCandidate, new: bool) -> None:
        for key, value in self.model_dump(exclude_none=True).items():
            setattr(saved_data, key, value)

        saved_data.save(force_insert=new)

    def refresh_user(self, saved_data: PromotionCandidate) -> bool:
        if self.last_checked and self.last_checked > (datetime.now() - timedelta(days=5)):  # noqa: DTZ005
            logger.info(f"User #{self.id} '{self.name}' was already checked recently.")
            return False

        self.last_checked = datetime.now(tz=UTC)
        logger.info(f"Populating missing values for user #{self.id} '{self.name}'.")

        db_user = DanbooruUser.get_from_name(self.name, cache=True)
        for key, value in self.from_danbooru_user(db_user).model_dump(exclude_none=True).items():
            setattr(self, key, value)

        last_edit = self.set_last_edit()
        self.populate_other_values(last_edit=last_edit, saved_data=saved_data)
        return True

    @classmethod
    def update_from_danbooru_user(cls, user: DanbooruUser) -> None:
        db_user = PromotionCandidate.get(user.id)
        user_data = IncompleteUserData.from_danbooru_user(user)
        for key, value in user_data.model_dump(exclude_none=True).items():
            setattr(db_user, key, value)
        db_user.save()

    def set_last_edit(self) -> datetime | None:
        versions = DanbooruPostVersion.get(updater_id=self.id, cache=True, limit=1)
        if versions:
            self.last_edit = versions[0].updated_at
            return versions[0].updated_at
        else:
            self.last_edit = DanbooruWikiPageVersion.get(updater_id=self.id, cache=True, limit=1)[0].updated_at
            return None

    def populate_other_values(self, last_edit: datetime | None, saved_data: PromotionCandidate) -> None:
        if self.total_posts == 0 or not last_edit:
            self.recent_posts = 0
            self.total_deleted_posts = 0
            self.recent_deleted_posts = 0
            self.low_gentag_posts = 0
        elif last_edit and last_edit < Defaults.RECENT_SINCE:
            # no point checking for recent posts
            self.recent_posts = 0
            self.recent_deleted_posts = 0
            self.low_gentag_posts = 0

            if saved_data.total_deleted_posts is None:
                count_search = DanbooruPostCounts.get(tags=f"status:deleted user:{self.name}",
                                                      cache=True)  # type: ignore[var-annotated] # one fucking job
                self.total_deleted_posts = count_search.count  # type: ignore[attr-defined]

        else:
            count_search = DanbooruPostCounts.get(tags=f"user:{self.name} date:{Defaults.RECENT_SINCE_STR}..",
                                                  cache=True)  # type: ignore[var-annotated] # one fucking job
            self.recent_posts = count_search.count

            count_search = DanbooruPostCounts.get(tags=f"status:deleted user:{self.name}",
                                                  cache=True)  # type: ignore[var-annotated] # one fucking job
            self.total_deleted_posts = count_search.count  # type: ignore[attr-defined]

            if self.recent_posts == 0:
                self.recent_deleted_posts = 0
                self.low_gentag_posts = 0
            else:
                count_search = DanbooruPostCounts.get(
                    tags=f"status:deleted user:{self.name} date:{Defaults.RECENT_SINCE_STR}..",
                    cache=True,
                )  # type: ignore[var-annotated] # one fucking job
                self.recent_deleted_posts = count_search.count      # type: ignore[attr-defined]

                count_search = DanbooruPostCounts.get(
                    tags=f"gentags:<15 -scenery -no_humans -abstract user:{self.name} date:{Defaults.RECENT_SINCE_STR}..",
                    cache=True,
                )  # type: ignore[var-annotated] # one fucking job
                self.low_gentag_posts = count_search.count      # type: ignore[attr-defined]

    def fetch_edit_data(self) -> dict:
        post_edits = DanbooruPostVersion.get_all(updater_name=self.name, is_new=False, max_pages=10)

        by_year = defaultdict(int)
        by_tag = defaultdict(lambda: {
            "added": 0,
            "removed": 0,
            "revert_added": 0,
            "revert_removed": 0,
        })

        for post_edit in post_edits:
            by_year[post_edit.updated_at.year] += 1

            for tag in post_edit.added_tags:
                by_tag[tag]["added"] += 1
            for tag in post_edit.removed_tags:
                by_tag[tag]["removed"] += 1
            for tag in post_edit.obsolete_added_tags:
                by_tag[tag]["revert_added"] += 1
            for tag in post_edit.obsolete_removed_tags:
                by_tag[tag]["revert_removed"] += 1

        by_tag = {k: v for k, v in by_tag.items() if v["added"] + v["removed"] > 50}
        by_tag = dict(sorted(by_tag.items(), key=lambda v: v[1]["added"] + v[1]["removed"], reverse=True))

        data = {
            "oldest": post_edits[-1].updated_at,
            "count": len(post_edits),
            "by_year": by_year,
            "by_tag":  by_tag,
        }

        return data

    def update_edit_data(self, update: bool = False) -> bool:
        if self.level > UserLevel("platinum"):
            logger.info(f"Edit data for user #{self.id} '{self.name}' won't be collected because they're already builder+.")
            return False
        if self.post_edits < 50:
            logger.info(f"Edit data for user #{self.id} '{self.name}' won't be collected because they have less than 50 edits.")
            return False

        try:
            last_edit = PromotionCandidate.get(self.id)
        except peewee.DoesNotExist:
            last_edit = datetime.now() - timedelta(weeks=52)  # noqa: DTZ005
        else:
            last_edit = last_edit.last_edit

        if last_edit < (datetime.now() - timedelta(days=60)):  # noqa: DTZ005
            logger.info(f"Edit data for user #{self.id} '{self.name}' won't be collected because they haven't edited in a long time.")
            return False

        try:
            edit_data = PromotionCandidateEdits.get(self.id)
        except peewee.DoesNotExist:
            edit_data = PromotionCandidateEdits(id=self.id)
            edit_data.last_checked = None

        force_insert = not edit_data.last_checked

        if not update:
            logger.info("Reached the limit for fetchable edit data in the current session. Skipping until next scan.")
            return False

        if edit_data.last_checked and edit_data.last_checked > (datetime.now() - timedelta(days=30)):  # noqa: DTZ005
            logger.info(f"Edit data for user #{self.id} '{self.name}' was already collected this month.")
            return False

        if edit_data.last_checked and edit_data.last_checked > last_edit:
            logger.info(f"Edit data for user #{self.id} '{self.name}' won't be collected because they haven't edited in a long time.")
            return False

        edit_data.last_checked = datetime.now(tz=UTC)
        logger.info(f"Populating edit data for user #{self.id} '{self.name}'.")

        edit_data.data = self.fetch_edit_data()

        edit_data.save(force_insert=force_insert)
        return True

    @field_validator("name", mode="after")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return value.replace(" ", "_")

    @staticmethod
    def from_danbooru_user(user: DanbooruUser) -> "IncompleteUserData":
        data = user.model_dump(exclude_none=True)
        extra_data = {
            "total_posts": user.post_upload_count,
            "total_note_edits": user.note_update_count,
            "post_edits": user.post_update_count,
            "level": user.level_string,
        }
        try:
            extra_data |= {
                "total_wiki_edits": user.wiki_page_version_count,
                "total_artist_edits": user.artist_version_count,
                "total_forum_posts": user.forum_post_count,
            }
        except WrongIncludeCallError:
            pass

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
    recent_uploader_data = DanbooruPostReport.get(**params, cache=True)  # type: ignore[arg-type]
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
    recent_uploader_data = DanbooruPostReport.get(**params, cache=True)  # type: ignore[arg-type]
    return [IncompleteUserData(name=r.uploader, recent_deleted_posts=r.posts, recently_active=True) for r in recent_uploader_data]


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
    for user_batch in batched(user_ids, 100):
        updated_users = DanbooruUser.get_all(id=",".join(map(str, user_batch)))
        for user in updated_users:
            IncompleteUserData.update_from_danbooru_user(user)


if __name__ == "__main__":
    populate_database()
