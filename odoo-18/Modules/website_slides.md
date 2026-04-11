# Website Slides Module (website_slides)

## Overview

The `website_slides` module provides an eLearning platform where courses (channels) contain slides (lessons). It supports video, document, article, infographic, and quiz content, with progress tracking, gamification (karma), and completion certificates.

## Key Models

### slide.channel

Represents a course/channel containing multiple slides.

**Inherits:** `mail.thread`, `website.seo.metadata`, `website.published.mixin`, `website.searchable.mixin`, `website.cover_properties.mixin`

**Key Fields:**
- `name`: Char - Course name
- `channel_type`: Selection - Type of channel: `training`, `documentation`, `podcast`
- `visibility`: Selection - Access control: `public`, `members`, `invite`
- `enroll`: Selection - Enrollment method: `public`, `login`, `invite`
- `upload_group_ids`: Many2many - User groups allowed to upload content
- `group_ids`: Many2many - Groups with access (for non-public channels)
- `slide_ids`: One2many - Slides in this channel
- `total_slides`: Integer - Total number of non-category slides (computed, stored)
- `total_slides_included`: Integer - Total including category slides
- `user_id`: Many2one - Responsible user/instructor
- `partner_ids`: Many2many - Members enrolled in this channel
- `members_all_ids`: Many2many - All members including archived (for history)
- `member_count`: Integer - Member count (computed)
- `komtu`: Boolean - Whether to enable "Know Other Members" feature
- `allow_comment`: Boolean - Allow discussion on slides
- `share_channel`: Boolean - Allow sharing the channel
- `share_slide`: Boolean - Allow sharing individual slides
- `publish_template_id`: Many2one - Email template for new slide notifications
- `completed_template_id`: Many2one - Email template for course completion

**Key Methods:**
- `_compute_slide_categories()`: Groups slides by category (document, video, article, infographic, quiz) and counts each type.
- `_compute_is_member()`: Checks if the current partner is a member of the channel.
- `_create_members(partner_ids)`: Creates `slide.channel.partner` records to enroll partners as members.
- `_remove_members(partner_ids)`: Archives `slide.channel.partner` records to unenroll members.
- `_get_remaining_and_total(slide_id)`: Returns remaining and total slide counts from a given slide position.
- `_get_next_slide()`: Returns the next unpublished slide after the current user's last completed slide.
- `_get_related_slides(slide, limit)`: Returns related slides for "More Like This" feature.
- `_upload_avatar(avatar)`: Updates the channel's avatar image from base64 data.
- `_add_template_filters()`: Creates default template slides for new courses.
- `_compute_website_url()`: Sets channel URL to `/slides/{slug}`.

### slide.channel.partner

The membership junction table linking partners to channels they are enrolled in. Also called "Channel Users Relation".

**Fields:**
- `active`: Boolean - Active membership status
- `channel_id`: Many2one - Parent channel
- `partner_id`: Many2one - Member partner
- `partner_email`: Char - Email (related, readonly)
- `member_status`: Selection - `invited`, `joined`, `ongoing`, `completed` (readonly, default `joined`)
- `completion`: Integer - Percentage of slides completed (0-100, stored, avg aggregation)
- `completed_slides_count`: Integer - Number of completed slides
- `next_slide_id`: Many2one - Next uncompleted slide for this member (computed via raw SQL)
- `channel_user_id`: Many2one - Related channel instructor
- `channel_type`, `channel_visibility`, `channel_enroll`, `channel_website_id`: Related channel info for UX
- `invitation_link`: Char - Unique URL for course invitation (computed via HMAC hash)
- `last_invitation_date`: Datetime - Last invitation email date

**Key Methods:**

- `_compute_invitation_link()`: Generates a signed invitation URL using an HMAC hash of `(partner_id, channel_id)` with the module's secret key. This URL is used in the channel invitation email.
- `_compute_next_slide_id()`: Raw SQL query finds the first unpublished, non-category slide in the channel that the member has not completed. Returns `False` if all slides are completed.
- `_recompute_completion()`: The core completion tracking method.
  - Finds all completed published slides for each channel/partner combination via `_read_group`
  - For each membership with status not in (`completed`, `invited`):
    - Computes `completed_slides_count`
    - Computes `completion = round(100 * completed_slides_count / total_slides)`
    - Updates `member_status`: `100%` -> `completed`, `0%` -> `joined`, else `ongoing`
  - When completion reaches 100% for the first time: triggers `_post_completion_update_hook(completed=True)` and `_send_completed_mail()`
  - When completion drops below 100% (slides unpublished): triggers `_post_completion_update_hook(completed=False)`
- `_post_completion_update_hook(completed)`: Awards or removes karma to users when they complete or un-complete a course. Karma amount is configured per channel (`karma_gen_channel_finish`). Calls `res.users._add_karma_batch()`.
- `_send_completed_mail()`: Sends a completion email to members who finished the course. Uses batched template rendering for efficiency.
- `_get_invitation_hash()`: Returns the HMAC-SHA256 hash used in the invitation link.
- `unlink()`: When deleting a membership, also deletes all `slide.slide.partner` records for that partner/channel combination.

**Status Transition:**
```
invited -> joined (when user accepts invitation and enrolls)
joined -> ongoing (when at least 1 slide is completed)
ongoing -> completed (when all slides are completed)
completed -> ongoing (if completion drops below 100%, e.g., slide unpublished)
```

### slide.slide

Represents an individual lesson/slide within a channel.

**Inherits:** `mail.thread`, `image.mixin`, `website.seo.metadata`, `website.published.mixin`, `website.searchable.mixin`

**Slide Categories (slide_category field):**
- `infographic`: Image content
- `article`: HTML article content
- `document`: PDF or Office document
- `video`: Video content (YouTube, Google Drive, Vimeo)
- `quiz`: Quiz with questions

**Content Fields:**
- `name`: Char - Slide title (required, translatable)
- `sequence`: Integer - Display order within the channel
- `description`: Html - Slide description
- `is_category`: Boolean - Whether this slide is a section header (category marker)
- `category_id`: Many2one - Parent category slide (for non-category slides)
- `slide_ids`: One2many - Child slides under a category
- `is_preview`: Boolean - Allow public access without joining the channel
- `is_new_slide`: Boolean - Marked as newly added (computed)
- `completion_time`: Float - Estimated duration in hours (recursive for categories)
- `date_published`: Datetime - When the slide was published

**Content Type Fields:**
- `slide_type`: Selection - Detailed type: `image`, `article`, `quiz`, `pdf`, `sheet`, `doc`, `slides`, `youtube_video`, `google_drive_video`, `vimeo_video` (computed from `slide_category` and `source_type`)
- `source_type`: Selection - `local_file` or `external` (Google Drive)
- `url`: Char - External URL (YouTube, Google Drive, Vimeo link)
- `binary_content`: Binary - Uploaded file content (PDF, images)
- `html_content`: Html - Custom HTML for article slides
- `slide_resource_ids`: One2many - Additional downloadable resources
- `slide_resource_downloadable`: Boolean - Allow resource downloads

**Quiz Fields:**
- `question_ids`: One2many - Questions for quiz slides
- `questions_count`: Integer - Number of questions
- `quiz_first_attempt_reward`: Integer - Karma reward for first attempt (default 10)
- `quiz_second_attempt_reward`: Integer - Karma reward for second attempt (default 7)
- `quiz_third_attempt_reward`: Integer - Karma reward for third attempt (default 5)
- `quiz_fourth_attempt_reward`: Integer - Karma reward for each subsequent attempt (default 2)

**User Membership Fields:**
- `slide_partner_ids`: One2many - Per-member completion/vote data
- `user_membership_id`: Many2one - Current user's membership record (computed)
- `user_vote`: Integer - Current user's like/dislike vote (-1, 0, 1)
- `user_has_completed`: Boolean - Whether current user has completed this slide
- `user_has_completed_category`: Boolean - Whether all slides in the category are completed

**Statistics Fields:**
- `slide_views`: Integer - Number of website views (stored)
- `public_views`: Integer - Views without authentication
- `total_views`: Integer - Sum of website and public views
- `likes`, `dislikes`: Integer - Vote counts (computed from `slide_partner_ids`)
- `embed_count`: Integer - Number of external embeds
- `comments_count`: Integer - Discussion thread comments

**Key Methods:**

- `_compute_user_membership_id()`: Finds the `slide.slide.partner` record for the current user/partner. Sets `user_vote` and `user_has_completed` from that record.
- `_compute_mark_complete_actions()`: Determines if the current user can self-mark this slide as complete/uncomplete based on slide type.
- `_compute_slide_type()`: Derives the `slide_type` from `slide_category` and URL patterns (YouTube, Google Drive, Vimeo detection).
- `_compute_total()`: Computes `total_views` as `slide_views + public_views`.
- `_compute_like_info()`: Aggregates vote values from `slide_partner_ids`.
- `_compute_slide_views()`: Counts records in `slide.embed` table for the slide.
- `_compute_embed_code()`: Generates an iframe embed code for video slides.
- `_compute_website_share_url()`: Returns the sharing URL for the slide.
- `_search_get_detail(website, order, options)`: Website search integration.

### slide.slide.partner

Junction table tracking per-member slide completion and votes. Also called "Slide Partner Relation".

**Fields:**
- `slide_id`: Many2one - The slide
- `channel_id`: Many2one - The channel (related from slide, stored for performance)
- `partner_id`: Many2one - The member
- `vote`: Integer - Vote: -1 (dislike), 0 (neutral), 1 (like)
- `completed`: Boolean - Whether the slide has been completed
- `quiz_attempts_count`: Integer - Number of quiz attempts

**SQL Constraints:**
- `slide_partner_uniq`: Unique partner-slide combination
- `check_vote`: Vote must be -1, 0, or 1

**Key Methods:**

- `write(values)`: When `completed` changes, triggers `_recompute_completion()` on all affected `slide.channel.partner` records.
- `_recompute_completion()`: Calls `_recompute_completion()` on all affected `slide.channel.partner` records (for the channel and partner of each updated slide-partner relation).

## Cross-Module Relationships

- **website**: Multi-website scoping, SEO, publication workflow, cover properties
- **mail**: Discussion threads on slides and channels
- **gamification**: Karma rewards for completing courses and quizzes
- **website_forum**: Discussion integration (if forum is enabled)
- **website_sale**: Course enrollment purchases (if eCommerce is enabled)

## Edge Cases

1. **Completion Tracking and Slide Unpublishing**: When a slide is unpublished, `_recompute_completion()` is triggered for affected memberships, potentially dropping completion below 100% and changing `member_status` from `completed` to `ongoing`. Karma previously awarded for completion is not automatically reversed.
2. **Invitation Link Security**: The invitation hash is an HMAC-SHA256 of `(partner_id, channel_id)` using a server-side secret. This allows invitation acceptance without the recipient needing to log in if the hash is valid.
3. **Quiz Attempt Rewards**: The karma reward for quiz completion decreases with each attempt (10, 7, 5, 2...). This is stored per slide and used in the quiz attempt handling code (in `slide.slide` completion logic).
4. **Category Slide Recursion**: Categories are slides with `is_category=True`. Their `completion_time` is the sum of all child slide times (recursive computed field).
5. **Public Preview**: `is_preview=True` allows non-members to view the slide content without joining the channel. This is useful for marketing course previews.
6. **Slide Sequence and Category Nesting**: Slides are ordered by `sequence` ascending, then category status, then ID. Category slides act as section headers and are excluded from completion counts.
7. **Visitor vs Partner Views**: `slide_views` tracks authenticated (visitor-tracked) views, while `public_views` counts views without visitor identification. Both contribute to `total_views`.
8. **Next Slide via Raw SQL**: `_compute_next_slide_id` uses a raw SQL query with `DISTINCT ON` and `NOT EXISTS` to efficiently find the first uncompleted published slide, avoiding N+1 issues.
9. **Channel COW Pattern**: Like other website content, channel pages use Odoo's Copy-on-Write (COW) pattern for per-website customization. Specific slides/menus can be overridden per website.
