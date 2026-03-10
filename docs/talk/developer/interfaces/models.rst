Data models
===========

The following are all of the relevant eventyay database models, including their
interfaces. All non-documented methods and properties should be considered
private and unstable. All methods and properties documented here may change
between releases, but any change will be mentioned in the release notes
starting with the 1.0 release.

All event related objects have an ``event`` property. It always returns the
event this object belongs to, to ease permission checks and reduce the need for
duplicate lookups.

Events and organisers
---------------------

.. autoclass:: eventyay.base.models.event.Event(*args, **kwargs)
   :members: cache,locales,is_multilingual,named_locales,plugin_list,enable_plugin,disable_plugin,pending_mails,wip_schedule,current_schedule,teams,datetime_from,datetime_to,talks,speakers,submitters,get_date_range_display,release_schedule,shred

.. autoclass:: eventyay.base.models.organizer.Organizer(*args, **kwargs)
   :members: shred

.. autoclass:: eventyay.base.models.organizer.Team(*args, **kwargs)
   :members: permission_set

.. autoclass:: eventyay.base.models.cfp.CfP(*args, **kwargs)
   :members: max_deadline,is_open

.. autoclass:: eventyay.base.models.review.ReviewPhase(*args, **kwargs)
   :members: activate

Users and profiles
------------------

.. autoclass:: eventyay.base.models.auth.User(*args, **kwargs)
   :members: get_display_name,event_profile,log_action,get_events_with_any_permission,get_events_for_permission,get_permissions_for_event

.. autoclass:: eventyay.base.models.profile.SpeakerProfile(*args, **kwargs)
   :members: submissions,talks,answers

.. autoclass:: eventyay.base.models.information.SpeakerInformation(*args, **kwargs)
   :members: id

Submissions
-----------

Submissions are the most central model to eventyay, and everything else is
connected to submissions.

.. autoclass:: eventyay.base.models.submission.Submission(*args, **kwargs)
   :members: get_duration,update_duration,update_talk_slots,make_submitted,confirm,accept,reject,cancel,withdraw,delete,public_slots,slot,display_speaker_names,median_score,availabilities

.. autoclass:: eventyay.base.models.review.Review(*args, **kwargs)
   :members: find_missing_reviews, display_score

.. autoclass:: eventyay.base.models.feedback.Feedback(*args, **kwargs)
   :members: id

.. autoclass:: eventyay.base.models.track.Track(*args, **kwargs)
   :members: slug

.. autoclass:: eventyay.base.models.type.SubmissionType(*args, **kwargs)
   :members: slug,update_duration

.. autoclass:: eventyay.base.models.resource.Resource(*args, **kwargs)
   :members: id

Questions and answers
---------------------

.. autoclass:: eventyay.base.models.question.TalkQuestion(*args, **kwargs)
   :members: missing_answers

.. autoclass:: eventyay.base.models.question.AnswerOption(*args, **kwargs)
   :members: id

.. autoclass:: eventyay.base.models.question.Answer(*args, **kwargs)
   :members: remove

Schedules and talk slots
------------------------

.. autoclass:: eventyay.base.models.schedule.Schedule(*args, **kwargs)
   :members: freeze,unfreeze,scheduled_talks,slots,previous_schedule,changes,warnings,speakers_concerned

.. autoclass:: eventyay.base.models.slot.TalkSlot(*args, **kwargs)
   :members: duration,real_end,as_availability,copy_to_schedule,is_same_slot

.. autoclass:: eventyay.base.models.availability.Availability(*args, **kwargs)
   :members: __eq__,all_day,overlaps,contains,merge_with,__or__,intersect_with,__and__,union,intersection

.. autoclass:: eventyay.base.models.room.Room(*args, **kwargs)
   :members: id

Emails and templates
--------------------

.. autoclass:: eventyay.base.models.mail.MailTemplate
   :members: to_mail

.. autoclass:: eventyay.base.models.mail.QueuedMail
   :members: send,copy_to_draft

Utility models
--------------

.. autoclass:: eventyay.base.models.log.ActivityLog
   :members: display
