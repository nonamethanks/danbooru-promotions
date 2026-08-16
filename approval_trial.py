from itertools import batched
from typing import TYPE_CHECKING

import click
from danbooru.models import DanbooruFavoriteGroup, DanbooruPost, DanbooruPostApproval
from danbooru.models.post_vote import DanbooruPostVote
from loguru import logger

if TYPE_CHECKING:
    import datetime


@click.command()
@click.argument("favgroup_str")
def main(favgroup_str: str) -> None:
    favgroup = DanbooruFavoriteGroup.from_url(favgroup_str)
    post_ids = list(set(favgroup.post_ids))


    approval_map: dict[int, datetime.datetime] = {}
    vote_map: dict[int, datetime.datetime] = {}
    all_posts: list[DanbooruPost] = []

    for post_batch in batched(post_ids, 50):
        id_list = ",".join(map(str, post_batch))
        approvals: list[DanbooruPostApproval] = DanbooruPostApproval.get(post_id=id_list)
        for approval in approvals:
            approval_map[approval.post_id] = approval.created_at

        votes: list[DanbooruPostVote] = DanbooruPostVote.get(post_id=id_list, user_id=favgroup.creator_id)
        for vote in votes:
            vote_map[vote.post_id] = vote.created_at

        post_details: list[DanbooruPost] = DanbooruPost.get(tags=[f"id:{id_list}"])
        all_posts += post_details

    unvoted = []
    active_when_added = []
    non_active = 0

    for post in all_posts:
        if post.is_deleted or post.is_pending or post.is_flagged:
            non_active += 1

        elif not vote_map.get(post.id):
            unvoted.append(post)

        elif not approval_map.get(post.id):
            active_when_added.append(post)

        elif approval_map[post.id] < vote_map[post.id]:
            active_when_added.append(post)

    invalid = list(set(unvoted + active_when_added))

    logger.info(f"Analyzed favgroup {favgroup_str}")
    logger.info(f"Posts in the favgroup: {len(post_ids)}")
    if unvoted:
        logger.info(f"{len(unvoted)} unvoted posts: {",".join(map(str, [p.id for p in unvoted]))}.")
    if active_when_added:
        logger.info(f"{len(active_when_added)} active when added posts: {",".join(map(str, [p.id for p in active_when_added]))}.")
    logger.info(f"{len(post_ids) - len(set(invalid + active_when_added))} valid posts.")

    logger.info(f"There are {non_active} non-active posts in the favgroup: https://danbooru.donmai.us/posts?tags=favgroup:{favgroup.id}+-status:active")



if __name__ == "__main__":
    main()
