
from datetime import UTC, datetime

from flask import Flask, render_template
from jinja2 import StrictUndefined
from peewee import DoesNotExist

from dbpromotions.database import PromotionCandidate, PromotionCandidateEdits, get_active_users

server = Flask(__name__)
server.jinja_env.undefined = StrictUndefined

CONTRIB_RISKY_DEL_COUNT = 20
CONTRIB_MAX_DEL_COUNT = 50
CONTRIB_MAX_DEL_PERC = 3
BUILDER_MAX_DEL_PERC = 15


@server.template_filter("days_ago")
def days_ago_int(dt: datetime | str) -> int:
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)

    return max((datetime.now(tz=UTC) - dt).days, 0)


@server.template_filter("weeks_ago_str")
def weeks_ago_str(dt: datetime | str) -> str:  # noqa: PLR0911
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


@server.template_filter("days_ago_str")
def days_ago_str(dt: datetime | str) -> str:
    days_ago = days_ago_int(dt)
    if days_ago == 0:
        return "today"
    elif days_ago < 31:
        return f"{days_ago} days ago"
    elif days_ago/31 < 12:
        return f"{days_ago//31 + 1} months ago"
    else:
        return f"{days_ago//365 + 1} years ago"


def get_last_updated() -> datetime:
    dt: datetime = PromotionCandidate.select(PromotionCandidate.last_checked) \
        .order_by(PromotionCandidate.last_checked.desc())             \
        .get().last_checked
    dt = dt.replace(tzinfo=UTC)
    return dt


@server.route("/")
def users() -> str:
    users = get_active_users()
    users = [u for u in users if u.should_be_considered]

    return render_template(
        "promotions.jinja2",
        last_updated=get_last_updated(),
        contrib_max_del_perc=CONTRIB_MAX_DEL_PERC,
        builder_max_del_perc=BUILDER_MAX_DEL_PERC,
        max_deleted_bad=CONTRIB_MAX_DEL_COUNT,
        max_deleted_warning=CONTRIB_RISKY_DEL_COUNT,
        users=users,
    )


@server.route("/users/<user_id>/edit_summary")
def user_edits(user_id: int) -> str:
    try:
        user_data = PromotionCandidateEdits.get(PromotionCandidateEdits.id == user_id)
    except DoesNotExist:
        return """
        <p style='color: red'><b>The edits report for this user is not (yet?) available.</b></p>
        <p>This data will only be available for levels below builder, and is being backpopulated,
          so it's gonna take a while to collect it for old entries.</p>
        """

    process_edit_data(user_data.data)

    return render_template(
        "edits_summary.jinja2",
        edits_data=user_data.data,
        user_id=user_id,
        last_checked=user_data.last_checked,
    )


def process_edit_data(data: dict) -> None:
    for tag_data in data["by_tag"].values():
        tag_data["total"] = tag_data["added"] + tag_data["removed"]
        tag_data["revert_total"] = tag_data["revert_added"] + tag_data["revert_removed"]

        tag_data["revert_total_perc"] = (tag_data["revert_total"] / tag_data["total"]) * 100

        if tag_data["added"]:
            tag_data["revert_added_perc"] = (tag_data["revert_added"] / tag_data["added"]) * 100
        else:
            tag_data["revert_added_perc"] = 0

        if tag_data["removed"]:
            tag_data["revert_removed_perc"] = (tag_data["revert_removed"] / tag_data["removed"]) * 100
        else:
            tag_data["revert_removed_perc"] = 0

        tag_data["bad_edits"] = False
        if tag_data["revert_total_perc"] > 15:
            tag_data["bad_edits"] = True
        if tag_data["revert_added_perc"] > 20 and tag_data["added"] > 20:
            tag_data["bad_edits"] = True
        if tag_data["revert_removed_perc"] > 20 and tag_data["removed"] > 20:
            tag_data["bad_edits"] = True
