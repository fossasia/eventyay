import pytest
import datetime as dt
from django.core import mail as djmail
from django_scopes import scope
from eventyay.base.models import Submission, SubmissionType, TalkQuestion, TalkQuestionVariant, TalkQuestionRequired, CfP, TalkQuestionTarget, SubmissionStates

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
            
            # Configure a required field in CfP
            event.cfp.fields["abstract"]["visibility"] = "required"
            event.cfp.save()
            return st

    def perform_init_wizard(self, client, event=None):
        url = f"/{event.organizer.slug}/{event.slug}/submit/"
        response = client.get(url, follow=True)
        print(f"\nDEBUG: init wizard GET status: {response.status_code}")
        # Check if it redirected to the first step (info)
        current_url = response.redirect_chain[-1][0] if response.redirect_chain else response.request.get('PATH_INFO', url)
        print(f"DEBUG: current url after init: {current_url}")
        return response, current_url

    def perform_info_wizard(self, client, response, url, submission_type=None, event=None, title="Test Title", action="submit"):
        data = {
            "title": title,
            "content_locale": "en",
            "submission_type": submission_type,
            "action": action,
        }
        res = client.post(url, data=data, follow=True)
        print(f"DEBUG: info wizard POST status: {res.status_code}, action: {action}")
        current_url = res.redirect_chain[-1][0] if res.redirect_chain else res.request.get('PATH_INFO', url)
        print(f"DEBUG: current url after info: {current_url}")
        return res, current_url

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
        print(f"DEBUG: draft post status: {response.status_code}")
        print(f"DEBUG: draft redirect chain: {response.redirect_chain}")
        print(f"DEBUG: final path info: {response.request.get('PATH_INFO')}")
        
        # Should redirect to submissions list (me/submissions)
        # If it failed validation and redirected back to info, we should see it
        assert "/me/submissions/" in response.request.get("PATH_INFO", ""), f"Did not reach submissions list. Final URL: {response.request.get('PATH_INFO')}. Content snippet: {response.content[:500].decode()}"
        
        # Verify submission exists in DRAFT state
        with scope(event=event):
            submissions = list(Submission.objects.all())
            print(f"DEBUG: Submissions in DB: {[s.title for s in submissions]}")
            submission = Submission.objects.filter(title="Minimal Draft Title").first()
            assert submission is not None, "Submission was not created"
            assert submission.state == SubmissionStates.DRAFT
            assert not submission.abstract, f"Abstract should be empty, got {submission.abstract}"

    @pytest.mark.django_db
    def test_save_draft_without_title(self, event, client, user, cfp_setup):
        """Verify that a draft is created even if title is missing, using a fallback."""
        client.force_login(user)
        submission_type = cfp_setup.pk

        # Start wizard
        response, current_url = self.perform_init_wizard(client, event=event)
        
        # Post with NO title and click "Save as draft"
        data = {
            "title": "",
            "action": "draft",
            "content_locale": "en",
            "submission_type": submission_type,
        }
        response = client.post(current_url, data=data, follow=True)
        
        # Should redirect to submissions list
        assert "/me/submissions/" in response.request.get("PATH_INFO", ""), f"Did not reach submissions list. Final URL: {response.request.get('PATH_INFO')}"
        
        # Verify submission exists with fallback title
        with scope(event=event):
            submission = Submission.objects.filter(state=SubmissionStates.DRAFT).last()
            assert submission is not None
            assert "Draft" in submission.title or "Untitled" in submission.title

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
        
        # Should NOT redirect to success page, but stay on info or redirect back to info
        assert "/me/submissions/" not in response.request.get("PATH_INFO", "")
        
        # Check if error message is in content
        content = response.content.decode().lower()
        assert "is required" in content or "required" in content

    @pytest.mark.django_db
    def test_save_draft_with_missing_questions(self, event, client, user, cfp_setup):
        """Verify that questions can be skipped when saving a draft."""
        client.force_login(user)
        submission_type = cfp_setup.pk
        
        with scope(event=event):
            # Create a required question
            q = TalkQuestion.objects.create(
                event=event,
                question="Required info",
                variant=TalkQuestionVariant.STRING,
                target=TalkQuestionTarget.SUBMISSION,
                question_required=TalkQuestionRequired.REQUIRED,
                position=1,
            )

        # Start wizard
        response, current_url = self.perform_init_wizard(client, event=event)
        
        # Fill info step and proceed to questions
        response, current_url = self.perform_info_wizard(
            client, response, current_url, submission_type=submission_type, event=event
        )
        
        assert "/questions/" in current_url
        
        # Now on questions step. Click "Save as draft" without answering question
        data = {
            "action": "draft",
        }
        response = client.post(current_url, data=data, follow=True)
        
        # Should redirect to submissions list
        assert "/me/submissions/" in response.request.get("PATH_INFO", "")
        
        # Verify it's a draft
        with scope(event=event):
            submission = Submission.objects.filter(title="Test Title").last()
            assert submission is not None
            assert submission.state == SubmissionStates.DRAFT
            assert submission.answers.count() == 0
