.. highlight:: python
   :linenothreshold: 5

Talk Component Models
=====================

These models are part of the unified eventyay Talk component, handling submissions, schedules, and speaker management.

Submissions
-----------

.. autoclass:: eventyay.base.models.Submission
   :members:

.. autoclass:: eventyay.base.models.SubmissionStates
   :members:

.. autoclass:: eventyay.base.models.SubmissionType
   :members:

.. autoclass:: eventyay.base.models.SubmissionFavourite
   :members:

Speakers
--------

.. autoclass:: eventyay.base.models.SpeakerProfile
   :members:

Schedule & Slots
----------------

.. autoclass:: eventyay.base.models.Schedule
   :members:

.. autoclass:: eventyay.base.models.TalkSlot
   :members:

.. autoclass:: eventyay.base.models.Track
   :members:

Call for Papers
---------------

.. autoclass:: eventyay.base.models.CfP
   :members:

Questions
---------

.. autoclass:: eventyay.base.models.TalkQuestion
   :members:

.. autoclass:: eventyay.base.models.TalkQuestionTarget
   :members:

.. autoclass:: eventyay.base.models.TalkQuestionVariant
   :members:

.. autoclass:: eventyay.base.models.Answer
   :members:

.. autoclass:: eventyay.base.models.AnswerOption
   :members:

Reviews
-------

.. autoclass:: eventyay.base.models.Review
   :members:

.. autoclass:: eventyay.base.models.ReviewPhase
   :members:

.. autoclass:: eventyay.base.models.ReviewScore
   :members:

.. autoclass:: eventyay.base.models.ReviewScoreCategory
   :members:

Tags & Resources
----------------

.. autoclass:: eventyay.base.models.Tag
   :members:
   :exclude-members: urls, DoesNotExist, MultipleObjectsReturned
   :undoc-members:
   :special-members: __str__

.. autoclass:: eventyay.base.models.Resource
   :members:

