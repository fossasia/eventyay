from eventyay.common.management.commands.backfill_images import IMAGE_TARGETS


def test_backfill_includes_remaining_image_fields():
    assert IMAGE_TARGETS['user'][1:] == ('avatar', True)
    assert IMAGE_TARGETS['profile_picture'][1:] == ('profile_picture', True)
    assert IMAGE_TARGETS['event_logo'][1] == 'logo'
    assert IMAGE_TARGETS['event_header_image'][1] == 'header_image'
    assert IMAGE_TARGETS['question_answer'][1] == 'answer_file'
    assert IMAGE_TARGETS['question_answer'][3] is True
    assert IMAGE_TARGETS['ticket_question_answer'][1] == 'file'
    assert IMAGE_TARGETS['ticket_question_answer'][3] is True
