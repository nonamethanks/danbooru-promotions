
from datetime import UTC, datetime

from danbooru.user_level import UserLevel
from flask import Flask, render_template
from jinja2 import StrictUndefined

from dbpromotions.database import PromotionCandidate

server = Flask(__name__)
server.jinja_env.undefined = StrictUndefined

CONTRIB_RISKY_DEL_COUNT = 20
CONTRIB_MAX_DEL_COUNT = 50
CONTRIB_MAX_DEL_PERC = 3
BUILDER_MAX_DEL_PERC = 15


@server.template_filter("days_ago")
def days_ago(dt: datetime) -> str:
    days_ago = (datetime.now(tz=UTC) - dt).days
    if days_ago == 0:
        days_ago_str = "today"
    elif days_ago > 365:
        days_ago_str = f"{days_ago//365} years ago"
    elif days_ago > 30:
        days_ago_str = f"{days_ago//30} months ago"
    else:
        days_ago_str = f"{days_ago} days ago"

    return days_ago_str


def get_users() -> list[PromotionCandidate]:
    return PromotionCandidate.select().where(PromotionCandidate.level < UserLevel.number_from_name("contributor"))


def get_last_updated() -> datetime:
    dt = PromotionCandidate.select(PromotionCandidate.last_checked) \
        .order_by(PromotionCandidate.last_checked.desc())             \
        .get().last_checked
    return datetime.fromisoformat(dt)


@server.route("/")
def hello() -> str:
    users = get_users()

    return render_template(
        "promotions.jinja2",
        last_updated=get_last_updated(),
        contrib_max_del_perc=CONTRIB_MAX_DEL_PERC,
        builder_max_del_perc=BUILDER_MAX_DEL_PERC,
        max_deleted_bad=CONTRIB_MAX_DEL_COUNT,
        max_deleted_warning=CONTRIB_RISKY_DEL_COUNT,

        builder_to_contributor=users,
    )
