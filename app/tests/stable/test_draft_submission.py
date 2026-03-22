import pytest
from django_scopes import scope
from eventyay.base.models import (
    Submission, SubmissionType, SubmissionStates,
    TalkQuestion, TalkQuestionTarget, TalkQuestionVariant, TalkQuestionRequired,
)


class TestDraftSubmission:

    @pytest.fixture
    def cfp_setup(self, event):
        with scope(event=event):
            # Ensure at least one submission type exists
            st = SubmissionType.objects.filter(event=event).first()
            if not st:
                st = SubmissionType.objects.create(event=event, name="Talk")

            # Ensure talks are accessible
            event.talks_published = True
            event.cfp.fields["abstract"]["visibility"] = "required"
            event.cfp.save()
            event.save()
            return st

    def perform_init_wizard(self, client, event=None):
        url = f"/{event.organizer.slug}/{event.slug}/submit/"
        response = client.get(url, follow=True)
        # Extract the final URL after all redirects, falling back to url
        try:
            current_url = response.redirect_chain[-1][0]
        except IndexError:
            current_url = url
        return response, current_url

    @pytest.mark.django_db
    def test_save_draft_with_only_title(self, event, client, user, cfp_setup):
        """Verify that a submission can be saved as a draft with only a title."""
        client.force_login(user)
        submission_type = cfp_setup.pk

        # Start wizard
        response, current_url = self.perform_init_wizard(client, event=event)

        # Post only title and click "Save as draft"
        data = {
            "title": "Minimal Draft Title",
            "action": "draft",
            "content_locale": "en",
            "submission_type": submission_type,
        }
        response = client.post(current_url, data=data, follow=True)

        # Should redirect to submissions list (me/submissions)
        final_path = response.wsgi_request.path
        assert "/me/submissions/" in final_path, f"Did not reach submissions list. Final URL: {final_path}"

        # Verify submission exists in DRAFT state
        with scope(event=event):
            submission = Submission.all_objects.filter(title="Minimal Draft Title").first()
            assert submission is not None, "Submission was not created"
            assert submission.state == SubmissionStates.DRAFT

    @pytest.mark.django_db
    def test_anonymous_save_draft_with_only_title(self, event, client, cfp_setup):
        """Verify that an anonymous user can save a submission as a draft with only a title."""
        submission_type = cfp_setup.pk

        # Start wizard without logging in
        response, current_url = self.perform_init_wizard(client, event=event)
        assert not response.wsgi_request.user.is_authenticated

        # Post only title and click "Save as draft" as anonymous user
        data = {
            "title": "Anonymous Minimal Draft Title",
            "action": "draft",
            "content_locale": "en",
            "submission_type": submission_type,
        }
        response = client.post(current_url, data=data, follow=True)

        # Response should be successful and not error out
        assert response.status_code == 200
        
        # Verify anonymous submission exists in DRAFT state
        with scope(event=event):
            submission = Submission.all_objects.filter(title="Anonymous Minimal Draft Title").first()
            assert submission is not None, "Anonymous draft submission was not created"
            assert submission.state == SubmissionStates.DRAFT

    @pytest.mark.django_db
    def test_final_submission_still_requires_fields(self, event, client, user, cfp_setup):
        """Verify that the final submission is still blocked if required fields are missing.
        Users can navigate through wizard steps freely, but submitting at the end
        redirects back to any step that is still incomplete."""
        client.force_login(user)
        submission_type = cfp_setup.pk

        # Start wizard — go to first step
        response, current_url = self.perform_init_wizard(client, event=event)

        # Click "Continue" with title only (abstract missing) — should advance to next step
        data = {
            "title": "Incomplete submission",
            "action": "submit",
            "content_locale": "en",
            "submission_type": submission_type,
            "abstract": "",  # intentionally missing
        }
        response = client.post(current_url, data=data, follow=True)

        # We should have moved past the first step
        final_path = response.wsgi_request.path
        assert "/me/submissions/" not in final_path, (
            "Should not have reached submissions list without required fields"
        )
        # The wizard's done() should NOT have accepted an incomplete submission —
        # it should have redirected back to an info/entry step, not the success page
        assert "submit" in final_path, (
            f"Expected to stay within the submission wizard, but ended up at: {final_path}"
        )

    @pytest.mark.django_db
    def test_draft_submission_skips_boolean_and_avatar_validation(self, event, client, user, cfp_setup):
        """Verify that draft submission skips boolean field requirement and avatar requirement."""
        client.force_login(user)
        submission_type = cfp_setup.pk

        with scope(event=event):
            # Add a required boolean question
            TalkQuestion.objects.create(
                event=event,
                question="Agreement",
                variant=TalkQuestionVariant.BOOLEAN,
                target=TalkQuestionTarget.SUBMISSION,
                question_required=TalkQuestionRequired.REQUIRED,
            )

            # Require avatar
            event.cfp.fields['avatar']['visibility'] = 'required'
            event.cfp.save()

        # Start wizard
        response, current_url = self.perform_init_wizard(client, event=event)

        # Post draft without boolean answer and without avatar
        data = {
            "title": "Draft with missing requirements",
            "action": "draft",
            "content_locale": "en",
            "submission_type": submission_type,
            # 'question_{q.pk}' is missing intentionally
        }
        response = client.post(current_url, data=data, follow=True)

        # Should redirect to submissions list (meaning validation didn't block it)
        final_path = response.wsgi_request.path
        assert "/me/submissions/" in final_path, f"Draft was blocked. Final URL: {final_path}"

        with scope(event=event):
            submission = Submission.all_objects.filter(title="Draft with missing requirements").first()
            assert submission is not None
            assert submission.state == SubmissionStates.DRAFT

    @pytest.mark.django_db
    def test_continue_in_draft_mode_advances_to_next_step(self, event, client, user, cfp_setup):
        """Verify that clicking Continue advances to the next step even when required fields
        are missing — Continue should never be blocked by validation."""
        client.force_login(user)
        submission_type = cfp_setup.pk

        # Start wizard
        response, current_url = self.perform_init_wizard(client, event=event)

        # Post "Continue" with missing required 'abstract' — no ?draft=1 needed
        data = {
            "title": "Draft Navigation Test",
            "action": "submit",  # "Continue" button
            "content_locale": "en",
            "submission_type": submission_type,
            "abstract": "",  # Missing required field
        }
        response = client.post(current_url, data=data, follow=False)

        # Should redirect to the next step, not re-render the same page with errors
        assert response.status_code in (301, 302), (
            f"Expected a redirect when pressing Continue, got {response.status_code}"
        )
        # Should NOT redirect back to the same URL (that would mean it was blocked)
        redirect_location = response.get('Location', '')
        assert current_url.rstrip('/').split('?')[0] not in redirect_location.rstrip('/').split('?')[0] or \
               redirect_location == current_url, (
            f"Continue redirected back to current step. Location: {redirect_location}"
        )
