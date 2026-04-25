from collections import defaultdict
from datetime import UTC, datetime, timedelta

import peewee
from danbooru.model import WrongIncludeCallError
from danbooru.models import DanbooruPostCounts, DanbooruPostVersion, DanbooruUser, DanbooruWikiPageVersion
from danbooru.user_level import UserLevel
from loguru import logger
from pydantic import BaseModel, field_validator

from dbpromotions import Defaults
from dbpromotions.database import PromotionCandidate, PromotionCandidateEdits


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
            fetched = False
        else:
            fetched = self.refresh_user(saved_data)

        self._save(saved_data, new=new)
        return fetched

    def _save(self, saved_data: PromotionCandidate, new: bool) -> None:
        for key, value in self.model_dump(exclude_none=True).items():
            setattr(saved_data, key, value)

        saved_data.save(force_insert=new)

    def refresh_user(self, saved_data: PromotionCandidate) -> bool:
        if self.last_checked and self.last_checked > (datetime.now() - timedelta(days=5)):
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

        wiki_versions = DanbooruWikiPageVersion.get(updater_id=self.id, cache=True, limit=1)
        if wiki_versions:
            self.last_edit = wiki_versions[0].updated_at

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
            last_edit = datetime.now() - timedelta(weeks=52)
        else:
            last_edit = last_edit.last_edit

        if last_edit < (datetime.now() - timedelta(days=60)):
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

        if edit_data.last_checked and edit_data.last_checked > (datetime.now() - timedelta(days=30)):
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
