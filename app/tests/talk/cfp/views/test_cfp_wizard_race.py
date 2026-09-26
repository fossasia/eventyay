import datetime as dt
import threading

import pytest
from django.db import connection
from django.test import Client
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import SubmissionType
from tests.talk.cfp.views.test_cfp_wizard import TestWizard


class TestWizardRace(TestWizard):
    @pytest.mark.django_db(transaction=True)
    def test_wizard_access_code_concurrent_submission(self, client, event, access_code):
        access_code.maximum_uses = 1
        access_code.save()

        with scope(event=event):
            submission_type = SubmissionType.objects.filter(event=event).first().pk

        # Close the CFP so that submission requires a valid access code
        event.cfp.deadline = now() - dt.timedelta(days=1)
        event.cfp.save()

        # Advance wizard state for the client up to the final step (profile)
        response, current_url = self.perform_init_wizard(
            client, event=event, access_code=access_code
        )
        response, current_url = self.perform_info_wizard(
            client,
            response,
            current_url,
            submission_type=submission_type,
            event=event,
            next_step="user",
        )
        response, current_url = self.perform_user_wizard(
            client,
            response,
            current_url,
            password="testpassw0rd!",
            email="testuser@example.com",
            register=True,
            event=event,
        )

        # Create a second client and clone the session
        client2 = Client()
        client2.cookies = client.cookies.copy()

        results = []
        barrier = threading.Barrier(2)

        def complete_wizard(c):
            try:
                barrier.wait()
                data = {"name": "Jane Doe", "biography": "l337 hax0r", "additional_speaker": ""}
                res = c.post(current_url, data, follow=True)
                success = False
                if res.redirect_chain:
                    final_url = res.redirect_chain[-1][0]
                    success = "/me/submissions" in final_url
                results.append(success)
            finally:
                connection.close()

        t1 = threading.Thread(target=complete_wizard, args=(client,))
        t2 = threading.Thread(target=complete_wizard, args=(client2,))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert results.count(True) <= 1, "Race condition allowed both submissions to complete!"

        access_code.refresh_from_db()
        assert access_code.redeemed == 1
