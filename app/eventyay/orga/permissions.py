import rules

from eventyay.talk_rules.event import can_change_event_settings
from eventyay.talk_rules.orga import enforces_hide_speaker_emails, enforces_hide_speaker_names, can_view_speaker_emails
from eventyay.talk_rules.submission import orga_can_change_submissions
from eventyay.talk_rules.person import is_reviewer

# Legacy for plugins. TODO remove after v2025.1.0
rules.add_perm('base.change_settings', can_change_event_settings)

rules.add_perm(
    'base.orga_view_speaker_emails', 
    ~enforces_hide_speaker_emails & ~enforces_hide_speaker_names & (orga_can_change_submissions | (is_reviewer & can_view_speaker_emails))
)
