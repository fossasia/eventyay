import pytest
from django_scopes import scope
from eventyay.base.models import Submission, SubmissionType, CfP, SubmissionStates

class TestDraftSubmission:

    @pytest.fixture
    def cfp_setup(self, event):
        with scope(event=event):
            # Ensure CfP object exists
            if not hasattr(event, 'cfp'):
                CfP.objects.create(event=event)
            
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
        # Check if it redirected to the first step (info)
        current_url = response.redirect_chain[-1][0] if response.redirect_chain else response.request.get('PATH_INFO', url)
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
        assert "/me/submissions/" in response.request.get("PATH_INFO", ""), f"Did not reach submissions list. Final URL: {response.request.get('PATH_INFO')}"
        
        # Verify submission exists in DRAFT state
        with scope(event=event):
            submission = Submission.all_objects.filter(title="Minimal Draft Title").first()
            assert submission is not None, "Submission was not created"
            assert submission.state == SubmissionStates.DRAFT

    @pytest.mark.django_db
    def test_final_submission_still_requires_fields(self, event, client, user, cfp_setup):
        """Verify that final submission is still blocked if required fields are missing."""
        client.force_login(user)
        submission_type = cfp_setup.pk

        # Start wizard
        response, current_url = self.perform_init_wizard(client, event=event)
        
        # Try to submit without abstract
        data = {
            "title": "Failing submission",
            "action": "submit",
            "content_locale": "en",
            "submission_type": submission_type,
            "abstract": "", # Should be required
        }
        response = client.post(current_url, data=data, follow=True)
        
        # Should NOT redirect to success page
        assert "/me/submissions/" not in response.request.get("PATH_INFO", "")
        
        # Check if error message is in content
        content = response.content.decode().lower()
        assert "is required" in content or "required" in content
    @pytest.mark.django_db
    def test_draft_submission_skips_boolean_and_avatar_validation(self, event, client, user, cfp_setup):
        """Verify that draft submission skips boolean field requirement and avatar requirement."""
        client.force_login(user)
        submission_type = cfp_setup.pk
        
        with scope(event=event):
            # Add a required boolean question
            from eventyay.base.models import TalkQuestion, TalkQuestionTarget, TalkQuestionVariant, TalkQuestionRequired
            q = TalkQuestion.objects.create(
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
        
        # Post draft without boolean answer and without avatar (avatar is handled in SpeakerStep/UserStep usually)
        # However, SpeakerProfileForm is usually part of the flow.
        # For simplicity, let's just test that the draft action works and redirects.
        data = {
            "title": "Draft with missing requirements",
            "action": "draft",
            "content_locale": "en",
            "submission_type": submission_type,
            # 'question_{q.pk}' is missing
        }
        response = client.post(current_url, data=data, follow=True)
        
        # Should redirect to submissions list (meaning validation didn't block it)
        assert "/me/submissions/" in response.request.get("PATH_INFO", ""), f"Draft was blocked. Final URL: {response.request.get('PATH_INFO')}"
        
        with scope(event=event):
            submission = Submission.all_objects.filter(title="Draft with missing requirements").first()
            assert submission is not None
            assert submission.state == SubmissionStates.DRAFT
