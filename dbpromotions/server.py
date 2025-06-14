
from datetime import UTC, datetime

from danbooru.user_level import UserLevel
from flask import Flask, render_template
from jinja2 import StrictUndefined

from dbpromotions import Defaults
from dbpromotions.database import PromotionCandidate

server = Flask(__name__)
server.jinja_env.undefined = StrictUndefined

CONTRIB_RISKY_DEL_COUNT = 20
CONTRIB_MAX_DEL_COUNT = 50
CONTRIB_MAX_DEL_PERC = 3
BUILDER_MAX_DEL_PERC = 15


@server.template_filter("days_ago")
def days_ago_int(dt: datetime) -> int:
    return max((datetime.now(tz=UTC) - dt).days, 0)


@server.template_filter("days_ago_str")
def days_ago_str(dt: datetime) -> str:
    days_ago = days_ago_int(dt)
    if days_ago == 0:
        return "today"
    elif days_ago < 7:
        return "this week"
    elif days_ago < 14:
        return "2 weeks ago"
    elif days_ago < 21:
        return "3 weeks ago"
    elif days_ago/31 <= 1:
        return "this month"
    elif days_ago/31 < 12:
        return f"{days_ago//30 + 1} months ago"
    else:
        return f"{days_ago//365 + 1} years ago"


def get_users() -> list[PromotionCandidate]:
    return PromotionCandidate.select() \
        .where(PromotionCandidate.level < UserLevel.number_from_name("contributor")) \
        .where(PromotionCandidate.last_edit > Defaults.RECENT_SINCE)


def get_last_updated() -> datetime:
    dt: datetime = PromotionCandidate.select(PromotionCandidate.last_checked) \
        .order_by(PromotionCandidate.last_checked.desc())             \
        .get().last_checked
    dt = dt.replace(tzinfo=UTC)
    return dt


@server.route("/")
def users() -> str:
    users = get_users()

    return render_template(
        "promotions.jinja2",
        last_updated=get_last_updated(),
        contrib_max_del_perc=CONTRIB_MAX_DEL_PERC,
        builder_max_del_perc=BUILDER_MAX_DEL_PERC,
        max_deleted_bad=CONTRIB_MAX_DEL_COUNT,
        max_deleted_warning=CONTRIB_RISKY_DEL_COUNT,
        users=users,
    )
