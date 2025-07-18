from datetime import UTC, datetime, timedelta

from danbooru.models import DanbooruPost, DanbooruPostVersion
from danbooru.user_level import UserLevel
from loguru import logger
from peewee import BooleanField, CharField, IntegerField, Model, SqliteDatabase, TimestampField

from dbpromotions import Defaults, Settings

user_database_location = Settings.DATA_FOLDER / "users.sqlite"
user_database = SqliteDatabase(user_database_location)


class PromotionCandidate(Model):
    class Meta:
        database = user_database

    id = IntegerField(primary_key=True)
    name = CharField()
    level = IntegerField(index=True)
    created_at = TimestampField()

    is_deleted = BooleanField()
    is_banned = BooleanField()

    last_checked = TimestampField()
    first_added = TimestampField(default=datetime.now)

    last_edit = TimestampField()

    total_posts = IntegerField(index=True)
    total_deleted_posts = IntegerField(index=True)

    recent_posts = IntegerField(index=True)
    recent_deleted_posts = IntegerField(index=True)

    post_edits = IntegerField(index=True)

    total_note_edits = IntegerField(index=True)
    # recent_note_edits = IntegerField(index=True)

    # total_wiki_edits = IntegerField(index=True)
    # recent_wiki_edits = IntegerField(index=True)

    # artist_edits = IntegerField(index=True)
    # recent_artist_edits = IntegerField(index=True)

    # forum_posts = IntegerField(index=True)
    # recent_forum_posts = IntegerField(index=True)

    # appeals = IntegerField(index=True)
    # recent_appeals = IntegerField(index=True)

    @property
    def html_classes(self) -> str:
        classes = ["user"]
        if self.is_banned:
            classes.append("banned")
        elif self.is_deleted:
            classes.append("deleted")
        classes.append(UserLevel.name_from_number(self.level).lower())  # type: ignore[arg-type]
        return " ".join(classes)

    @property
    def url(self) -> str:
        return f"https://danbooru.donmai.us/users/{self.id}"

    @property
    def promote_url(self) -> str:
        return f"https://danbooru.donmai.us/admin/users/{self.id}/edit"

    @property
    def post_edits_url(self) -> str:
        return DanbooruPostVersion.url_for(updater_id=self.id, limit=20)

    @property
    def recent_posts_url(self) -> str:
        return DanbooruPost.url_for(tags=f"user:{self.name} date:{Defaults.RECENT_SINCE_STR}..")

    @property
    def recent_deleted_posts_url(self) -> str:
        return DanbooruPost.url_for(tags=f"user:{self.name} status:deleted date:{Defaults.RECENT_SINCE_STR}..")

    @property
    def note_edits_url(self) -> str:
        return f"https://danbooru.donmai.us/note_versions?search[updater_id]={self.id}"

    @property
    def total_delete_ratio(self) -> int:
        if self.total_posts == 0:
            return 0
        return (self.total_deleted_posts / self.total_posts) * 100  # type: ignore[return-value]

    @property
    def recent_delete_ratio(self) -> int:
        if self.recent_posts == 0:
            return 0
        return (self.recent_deleted_posts / self.recent_posts) * 100  # type: ignore[return-value]

    @property
    def html_total_deletion_ratio(self) -> str:
        return f"{self.total_delete_ratio:.2f}"

    @property
    def html_recent_deletion_ratio(self) -> str:
        return f"{self.recent_delete_ratio:.2f}"

    @property
    def level_string(self) -> str:
        return UserLevel.name_from_number(self.level)

    @property
    def last_edit_dt(self) -> datetime:
        dt = self.last_edit
        dt = dt.replace(tzinfo=UTC)
        return dt

    @property
    def first_added_dt(self) -> datetime:
        dt = self.first_added
        dt = dt.replace(tzinfo=UTC)
        return dt

    @property
    def should_be_considered(self) -> bool:
        if self.total_posts > Defaults.MIN_UPLOADS:
            return True

        if self.post_edits > Defaults.MIN_EDITS or self.total_note_edits > Defaults.MIN_NOTES:  # noqa: SIM102
            if self.level < UserLevel.number_from_name("builder"):
                return True

        return False


def init_database() -> None:
    logger.debug("Initializing database...")
    user_database_location.parent.mkdir(exist_ok=True)
    with user_database:
        logger.debug("Initializing tables...")
        user_database.create_tables([PromotionCandidate])


def get_active_users() -> list[PromotionCandidate]:
    users = PromotionCandidate.select() \
        .where(PromotionCandidate.level < UserLevel.number_from_name("contributor"))

    users = filter(was_active_recently, users)

    return list(users)


def was_active_recently(user: PromotionCandidate) -> bool:
    return user.last_checked - user.last_edit < Defaults.RECENT_RANGE
