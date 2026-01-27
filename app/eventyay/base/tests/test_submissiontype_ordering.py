from django.test import TestCase
from django_scopes import scope
from eventyay.base.models import Event, SubmissionType, Organizer

class SubmissionTypeOrderingTestCase(TestCase):
    
    def setUp(self):
        self.organizer = Organizer.objects.create(name='Test Org', slug='test-org')
        from django.utils import timezone
        self.event = Event.objects.create(
            organizer=self.organizer,
            name='Test Event',
            slug='test-event',
            date_from=timezone.now(),
            date_to=timezone.now() + timezone.timedelta(days=1)
        )
    
    def test_default_ordering_by_position(self):
        """Test that SubmissionTypes are ordered by position by default"""
        with scope(event=self.event):
            # Reuse default type
            type1 = self.event.submission_types.first()
            type1.name = 'Type 1'
            type1.position = 3
            type1.save()

            type2 = SubmissionType.objects.create(
                event=self.event,
                name='Type 2',
                position=1
            )
            type3 = SubmissionType.objects.create(
                event=self.event,
                name='Type 3',
                position=2
            )
            
            types = list(self.event.submission_types.all())
            self.assertEqual(types[0], type2)  # position=1
            self.assertEqual(types[1], type3)  # position=2
            self.assertEqual(types[2], type1)  # position=3
    
    def test_position_auto_assigned_on_create(self):
        """Test that position is automatically assigned when creating new type"""
        with scope(event=self.event):
            # Default type exists and likely has position 0 or 1
            initial_count = self.event.submission_types.count()
            
            type1 = SubmissionType.objects.create(
                event=self.event,
                name='New Type 1'
            )
            self.assertIsNotNone(type1.position)
            self.assertGreater(type1.position, 0)
            
            type2 = SubmissionType.objects.create(
                event=self.event,
                name='New Type 2'
            )
            self.assertGreater(type2.position, type1.position)
    
    def test_queryset_respects_position_order(self):
        """Test that view querysets return types in position order"""
        with scope(event=self.event):
            # Clear default by updating it to be 'C'
            t_c = self.event.submission_types.first()
            t_c.name = 'C'
            t_c.position = 30
            t_c.save()

            SubmissionType.objects.create(event=self.event, name='A', position=10)
            SubmissionType.objects.create(event=self.event, name='B', position=20)
            
            types = self.event.submission_types.all()
            names = [t.name for t in types]
            self.assertEqual(names, ['A', 'B', 'C'])
    
    def test_default_duration_sorting_preserves_order(self):
        """Test that manual sorting by default_duration preserves expected order"""
        with scope(event=self.event):
            # Reuse default as Short
            type1 = self.event.submission_types.first()
            type1.name = 'Short'
            type1.default_duration = 15
            # Reset position to simulate unsorted state
            type1.position = 0

            type1.save()

            type2 = SubmissionType.objects.create(
                event=self.event,
                name='Long',
                default_duration=60,
                position=0
            )

            # Manually apply the same ordering logic used for assigning positions
            types = self.event.submission_types.all().order_by('default_duration', 'id')
            for index, t in enumerate(types, start=1):
                t.position = index
                t.save()
            # Verify order
            ordered_types = list(self.event.submission_types.all())
            self.assertEqual(ordered_types[0].name, 'Short')
            self.assertEqual(ordered_types[1].name, 'Long')

    def test_update_position_to_zero(self):
        """Test that updating position to 0 is respected"""
        with scope(event=self.event):
            type1 = SubmissionType.objects.create(event=self.event, name='T1', position=10)
            type1.position = 0
            type1.save()
            type1.refresh_from_db()
            self.assertEqual(type1.position, 0)
