import datetime
from decimal import Decimal

import pytest
from django import forms
from django.test import override_settings
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled
from i18nfield.strings import LazyI18nString

from eventyay.control.forms.product import ProductCreateForm, clean_free_price_bounds

from eventyay.base.models import (
    Event,
    Product as Item,
    ProductCategory as ItemCategory,
    ProductVariation as ItemVariation,
    Order,
    OrderPosition,
    Organizer,
    Question,
    Quota,
    Team,
    User,
)
from tests.tickets.base import SoupTest, extract_form_fields


class ItemFormTest(SoupTest):
    @scopes_disabled()
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user('dummy@dummy.dummy', 'dummy')
        self.orga1 = Organizer.objects.create(name='CCC', slug='ccc')
        self.orga2 = Organizer.objects.create(name='MRM', slug='mrm')
        self.event1 = Event.objects.create(
            organizer=self.orga1,
            name='30C3',
            slug='30c3',
            date_from=datetime.datetime(2013, 12, 26, tzinfo=datetime.timezone.utc),
        )
        self.item1 = Item.objects.create(event=self.event1, name='Standard', default_price=0, position=1)
        t = Team.objects.create(organizer=self.orga1, can_change_event_settings=True, can_change_items=True)
        t.members.add(self.user)
        t.limit_events.add(self.event1)
        self.client.login(email='dummy@dummy.dummy', password='dummy')


class CategoriesTest(ItemFormTest):
    def test_create(self):
        doc = self.get_doc('/control/event/%s/%s/categories/add' % (self.orga1.slug, self.event1.slug))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['name_0'] = 'Entry tickets'
        doc = self.post_doc(
            '/control/event/%s/%s/categories/add' % (self.orga1.slug, self.event1.slug),
            form_data,
        )
        assert doc.select('.alert-success')
        self.assertIn('Entry tickets', doc.select('#page-wrapper table')[0].text)

    def test_update(self):
        c = ItemCategory.objects.create(event=self.event1, name='Entry tickets')
        doc = self.get_doc('/control/event/%s/%s/categories/%s/' % (self.orga1.slug, self.event1.slug, c.id))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['name_0'] = 'T-Shirts'
        doc = self.post_doc(
            '/control/event/%s/%s/categories/%s/' % (self.orga1.slug, self.event1.slug, c.id),
            form_data,
        )
        assert doc.select('.alert-success')
        self.assertIn('T-Shirts', doc.select('#page-wrapper table')[0].text)
        self.assertNotIn('Entry tickets', doc.select('#page-wrapper table')[0].text)
        with scopes_disabled():
            assert str(ItemCategory.objects.get(id=c.id).name) == 'T-Shirts'

    def test_sort(self):
        with scopes_disabled():
            c1 = ItemCategory.objects.create(event=self.event1, name='Entry tickets', position=0)
            ItemCategory.objects.create(event=self.event1, name='T-Shirts', position=1)
        doc = self.get_doc('/control/event/%s/%s/categories/' % (self.orga1.slug, self.event1.slug))
        self.assertIn('Entry tickets', doc.select('table > tbody > tr')[0].text)
        self.assertIn('T-Shirts', doc.select('table > tbody > tr')[1].text)

        self.client.get('/control/event/%s/%s/categories/%s/down' % (self.orga1.slug, self.event1.slug, c1.id))
        doc = self.get_doc('/control/event/%s/%s/categories/' % (self.orga1.slug, self.event1.slug))
        self.assertIn('Entry tickets', doc.select('table > tbody > tr')[1].text)
        self.assertIn('T-Shirts', doc.select('table > tbody > tr')[0].text)

        self.client.get('/control/event/%s/%s/categories/%s/up' % (self.orga1.slug, self.event1.slug, c1.id))
        doc = self.get_doc('/control/event/%s/%s/categories/' % (self.orga1.slug, self.event1.slug))
        self.assertIn('Entry tickets', doc.select('table > tbody > tr')[0].text)
        self.assertIn('T-Shirts', doc.select('table > tbody > tr')[1].text)

    def test_delete(self):
        with scopes_disabled():
            c = ItemCategory.objects.create(event=self.event1, name='Entry tickets')
        doc = self.get_doc('/control/event/%s/%s/categories/%s/delete' % (self.orga1.slug, self.event1.slug, c.id))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        doc = self.post_doc(
            '/control/event/%s/%s/categories/%s/delete' % (self.orga1.slug, self.event1.slug, c.id),
            form_data,
        )
        assert doc.select('.alert-success')
        self.assertNotIn('Entry tickets', doc.select('#page-wrapper')[0].text)
        with scopes_disabled():
            assert not ItemCategory.objects.filter(id=c.id).exists()


class QuestionsTest(ItemFormTest):
    def test_create(self):
        doc = self.get_doc('/control/event/%s/%s/questions/add' % (self.orga1.slug, self.event1.slug))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['question_0'] = 'What is your shoe size?'
        form_data['type'] = 'N'
        form_data['items'] = self.item1.id
        doc = self.post_doc(
            '/control/event/%s/%s/questions/add' % (self.orga1.slug, self.event1.slug),
            form_data,
        )
        assert doc.select('.alert-success')
        self.assertIn('shoe size', doc.select('#page-wrapper table')[0].text)

    def test_update_choices(self):
        with scopes_disabled():
            c = Question.objects.create(
                event=self.event1,
                question='What country are you from?',
                type='C',
                required=True,
            )
            o1 = c.options.create(answer='Germany')
        doc = self.get_doc('/control/event/%s/%s/questions/%s/change' % (self.orga1.slug, self.event1.slug, c.id))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['form-TOTAL_FORMS'] = '1'
        form_data['form-INITIAL_FORMS'] = '1'
        form_data['form-MIN_NUM_FORMS'] = '0'
        form_data['form-MAX_NUM_FORMS'] = '1'
        form_data['form-0-id'] = o1.pk
        form_data['items'] = self.item1.id
        form_data['form-0-answer_0'] = 'England'
        self.post_doc(
            '/control/event/%s/%s/questions/%s/change' % (self.orga1.slug, self.event1.slug, c.id),
            form_data,
        )
        c.refresh_from_db()
        with scopes_disabled():
            assert c.options.exists()
            assert str(c.options.first().answer) == 'England'

    def test_delete_choices(self):
        with scopes_disabled():
            c = Question.objects.create(
                event=self.event1,
                question='What country are you from?',
                type='C',
                required=True,
            )
            o1 = c.options.create(answer='Germany')
        doc = self.get_doc('/control/event/%s/%s/questions/%s/change' % (self.orga1.slug, self.event1.slug, c.id))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['form-TOTAL_FORMS'] = '1'
        form_data['form-INITIAL_FORMS'] = '1'
        form_data['form-MIN_NUM_FORMS'] = '0'
        form_data['form-MAX_NUM_FORMS'] = '1'
        form_data['items'] = self.item1.id
        form_data['form-0-id'] = o1.pk
        form_data['form-0-answer_0'] = 'England'
        form_data['form-0-DELETE'] = 'yes'
        self.post_doc(
            '/control/event/%s/%s/questions/%s/change' % (self.orga1.slug, self.event1.slug, c.id),
            form_data,
        )
        c.refresh_from_db()
        with scopes_disabled():
            assert not c.options.exists()

    def test_add_choices(self):
        with scopes_disabled():
            c = Question.objects.create(
                event=self.event1,
                question='What country are you from?',
                type='N',
                required=True,
            )
        doc = self.get_doc('/control/event/%s/%s/questions/%s/change' % (self.orga1.slug, self.event1.slug, c.id))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['type'] = 'C'
        form_data['form-TOTAL_FORMS'] = '1'
        form_data['form-INITIAL_FORMS'] = '0'
        form_data['form-MIN_NUM_FORMS'] = '0'
        form_data['form-MAX_NUM_FORMS'] = '1'
        form_data['items'] = self.item1.id
        form_data['form-0-id'] = ''
        form_data['form-0-answer_0'] = 'Germany'
        self.post_doc(
            '/control/event/%s/%s/questions/%s/change' % (self.orga1.slug, self.event1.slug, c.id),
            form_data,
        )
        with scopes_disabled():
            c = Question.objects.get(id=c.id)
            assert c.options.exists()
            assert str(c.options.first().answer) == 'Germany'

    def test_update(self):
        with scopes_disabled():
            c = Question.objects.create(
                event=self.event1,
                question='What is your shoe size?',
                type='N',
                required=True,
            )
        doc = self.get_doc('/control/event/%s/%s/questions/%s/change' % (self.orga1.slug, self.event1.slug, c.id))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['items'] = self.item1.id
        form_data['question_0'] = 'How old are you?'
        doc = self.post_doc(
            '/control/event/%s/%s/questions/%s/change' % (self.orga1.slug, self.event1.slug, c.id),
            form_data,
        )
        self.assertIn('How old', doc.select('#page-wrapper table')[0].text)
        self.assertNotIn('shoe size', doc.select('#page-wrapper table')[0].text)
        with scopes_disabled():
            c = Question.objects.get(id=c.id)
            self.assertTrue(c.required)
            assert str(Question.objects.get(id=c.id).question) == 'How old are you?'

    def test_delete(self):
        with scopes_disabled():
            c = Question.objects.create(
                event=self.event1,
                question='What is your shoe size?',
                type='N',
                required=True,
            )
        doc = self.get_doc('/control/event/%s/%s/questions/%s/delete' % (self.orga1.slug, self.event1.slug, c.id))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        doc = self.post_doc(
            '/control/event/%s/%s/questions/%s/delete' % (self.orga1.slug, self.event1.slug, c.id),
            form_data,
        )
        assert doc.select('.alert-success')
        self.assertNotIn('shoe size', doc.select('#page-wrapper')[0].text)
        with scopes_disabled():
            assert not Question.objects.filter(id=c.id).exists()

    def test_question_view(self):
        with scopes_disabled():
            c = Question.objects.create(
                event=self.event1,
                question='What is your shoe size?',
                type='N',
                required=True,
            )

            item1 = Item.objects.create(event=self.event1, name='Standard', default_price=0, position=1)
            o = Order.objects.create(
                code='FOO',
                event=self.event1,
                email='dummy@dummy.test',
                status=Order.STATUS_PENDING,
                datetime=now(),
                expires=now() + datetime.timedelta(days=10),
                total=14,
                locale='en',
            )
            op = OrderPosition.objects.create(
                order=o,
                item=item1,
                variation=None,
                price=Decimal('14'),
                attendee_name_parts={'full_name': 'Peter'},
            )
            op.answers.create(question=c, answer='42')
            op = OrderPosition.objects.create(
                order=o,
                item=item1,
                variation=None,
                price=Decimal('14'),
                attendee_name_parts={'full_name': 'Michael'},
            )
            op.answers.create(question=c, answer='42')
            op = OrderPosition.objects.create(
                order=o,
                item=item1,
                variation=None,
                price=Decimal('14'),
                attendee_name_parts={'full_name': 'Petra'},
            )
            op.answers.create(question=c, answer='39')

        doc = self.get_doc('/control/event/%s/%s/questions/%s/' % (self.orga1.slug, self.event1.slug, c.id))
        tbl = doc.select('.container-fluid table.table-bordered tbody')[0]
        assert tbl.select('tr')[0].select('td')[0].text.strip() == '42'
        assert tbl.select('tr')[0].select('td')[1].text.strip() == '2'
        assert tbl.select('tr')[1].select('td')[0].text.strip() == '39'
        assert tbl.select('tr')[1].select('td')[1].text.strip() == '1'

        doc = self.get_doc('/control/event/%s/%s/questions/%s/?status=p' % (self.orga1.slug, self.event1.slug, c.id))
        assert not doc.select('.container-fluid table.table-bordered tbody')

        o.status = Order.STATUS_PAID
        o.save()
        doc = self.get_doc('/control/event/%s/%s/questions/%s/?status=p' % (self.orga1.slug, self.event1.slug, c.id))
        tbl = doc.select('.container-fluid table.table-bordered tbody')[0]
        assert tbl.select('tr')[0].select('td')[0].text.strip() == '42'

    def test_set_dependency(self):
        with scopes_disabled():
            q1 = Question.objects.create(
                event=self.event1,
                question='What country are you from?',
                type='C',
                required=True,
            )
            q2 = Question.objects.create(
                event=self.event1,
                question='What city are you from?',
                type='T',
                required=True,
            )
            o1 = q1.options.create(answer='Germany')
        doc = self.get_doc('/control/event/%s/%s/questions/%s/change' % (self.orga1.slug, self.event1.slug, q2.id))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['items'] = self.item1.id
        form_data['dependency_question'] = q1.pk
        form_data['dependency_values'] = o1.identifier
        doc = self.post_doc(
            '/control/event/%s/%s/questions/%s/change' % (self.orga1.slug, self.event1.slug, q2.id),
            form_data,
        )
        assert doc.select('.alert-success')
        q2.refresh_from_db()
        assert q2.dependency_question == q1
        assert q2.dependency_values == [o1.identifier]

    def test_set_dependency_circular(self):
        with scopes_disabled():
            q1 = Question.objects.create(
                event=self.event1,
                question='What country are you from?',
                type='C',
                required=True,
            )
            o1 = q1.options.create(answer='Germany')
            q2 = Question.objects.create(
                event=self.event1,
                question='What city are you from?',
                type='C',
                required=True,
                dependency_question=q1,
                dependency_values=[o1.identifier],
            )
        doc = self.get_doc('/control/event/%s/%s/questions/%s/change' % (self.orga1.slug, self.event1.slug, q1.id))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['dependency_question'] = q2.pk
        form_data['dependency_values'] = '1'
        doc = self.post_doc(
            '/control/event/%s/%s/questions/%s/change' % (self.orga1.slug, self.event1.slug, q1.id),
            form_data,
        )
        assert not doc.select('.alert-success')

    def test_set_dependency_to_non_choice(self):
        with scopes_disabled():
            q1 = Question.objects.create(
                event=self.event1,
                question='What country are you from?',
                type='N',
                required=True,
            )
            q2 = Question.objects.create(
                event=self.event1,
                question='What city are you from?',
                type='T',
                required=True,
            )
        doc = self.get_doc('/control/event/%s/%s/questions/%s/change' % (self.orga1.slug, self.event1.slug, q2.id))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['dependency_question'] = q1.pk
        form_data['dependency_values'] = '1'
        doc = self.post_doc(
            '/control/event/%s/%s/questions/%s/change' % (self.orga1.slug, self.event1.slug, q2.id),
            form_data,
        )
        assert not doc.select('.alert-success')


class QuotaTest(ItemFormTest):
    def test_create(self):
        doc = self.get_doc('/control/event/%s/%s/quotas/add' % (self.orga1.slug, self.event1.slug))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['name'] = 'Full house'
        form_data['size'] = '500'
        doc = self.post_doc(
            '/control/event/%s/%s/quotas/add' % (self.orga1.slug, self.event1.slug),
            form_data,
        )
        assert doc.select('.alert-success')
        self.assertIn('Full house', doc.select('#page-wrapper table')[0].text)

    def test_update(self):
        with scopes_disabled():
            c = Quota.objects.create(event=self.event1, name='Full house', size=500)
            item1 = Item.objects.create(event=self.event1, name='Standard', default_price=0)
            item2 = Item.objects.create(event=self.event1, name='Business', default_price=0)
            ItemVariation.objects.create(item=item2, value='Silver')
            ItemVariation.objects.create(item=item2, value='Gold')
        doc = self.get_doc('/control/event/%s/%s/quotas/%s/change' % (self.orga1.slug, self.event1.slug, c.id))
        [i for i in doc.select('[name=itemvars]') if i.get('value') == str(item1.id)][0]['checked'] = 'checked'
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['size'] = '350'
        doc = self.post_doc(
            '/control/event/%s/%s/quotas/%s/change' % (self.orga1.slug, self.event1.slug, c.id),
            form_data,
        )
        doc = self.get_doc('/control/event/%s/%s/quotas/' % (self.orga1.slug, self.event1.slug))
        self.assertIn('350', doc.select('#page-wrapper table')[0].text)
        self.assertNotIn('500', doc.select('#page-wrapper table')[0].text)
        with scopes_disabled():
            assert Quota.objects.get(id=c.id).size == 350
            assert item1 in Quota.objects.get(id=c.id).items.all()

    def test_update_subevent(self):
        self.event1.has_subevents = True
        self.event1.save()
        with scopes_disabled():
            se1 = self.event1.subevents.create(name='Foo', date_from=now())
            se2 = self.event1.subevents.create(name='Bar', date_from=now())
            c = Quota.objects.create(event=self.event1, name='Full house', size=500, subevent=se1)
        doc = self.get_doc('/control/event/%s/%s/quotas/%s/change' % (self.orga1.slug, self.event1.slug, c.id))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['subevent'] = se2.pk
        self.post_doc(
            '/control/event/%s/%s/quotas/%s/change' % (self.orga1.slug, self.event1.slug, c.id),
            form_data,
        )
        with scopes_disabled():
            assert Quota.objects.get(id=c.id).subevent == se2

    def test_delete(self):
        with scopes_disabled():
            c = Quota.objects.create(event=self.event1, name='Full house', size=500)
        doc = self.get_doc('/control/event/%s/%s/quotas/%s/delete' % (self.orga1.slug, self.event1.slug, c.id))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        doc = self.post_doc(
            '/control/event/%s/%s/quotas/%s/delete' % (self.orga1.slug, self.event1.slug, c.id),
            form_data,
        )
        assert doc.select('.alert-success')
        self.assertNotIn('Full house', doc.select('#page-wrapper')[0].text)
        with scopes_disabled():
            assert not Quota.objects.filter(id=c.id).exists()

    def test_reopen(self):
        with scopes_disabled():
            c = Quota.objects.create(
                event=self.event1,
                name='Full house',
                size=500,
                close_when_sold_out=True,
                closed=True,
            )
        self.post_doc(
            '/control/event/%s/%s/quotas/%s/' % (self.orga1.slug, self.event1.slug, c.id),
            {'reopen': 'true'},
        )
        with scopes_disabled():
            c.refresh_from_db()
            assert not c.closed
            assert c.close_when_sold_out

    def test_reopen_and_disable(self):
        with scopes_disabled():
            c = Quota.objects.create(
                event=self.event1,
                name='Full house',
                size=500,
                close_when_sold_out=True,
                closed=True,
            )
        self.post_doc(
            '/control/event/%s/%s/quotas/%s/' % (self.orga1.slug, self.event1.slug, c.id),
            {'disable': 'true'},
        )
        with scopes_disabled():
            c.refresh_from_db()
            assert not c.closed
            assert not c.close_when_sold_out


class ItemsTest(ItemFormTest):
    @scopes_disabled()
    def setUp(self):
        super().setUp()
        self.item2 = Item.objects.create(
            event=self.event1,
            name='Business',
            default_price=0,
            position=2,
            description='If your ticket is paid by your employer',
            active=True,
            available_until=now() + datetime.timedelta(days=4),
            require_voucher=True,
            allow_cancel=False,
        )
        self.var1 = ItemVariation.objects.create(item=self.item2, value='Silver')
        self.var2 = ItemVariation.objects.create(item=self.item2, value='Gold')
        self.addoncat = ItemCategory.objects.create(event=self.event1, name='Item category')

    def test_move(self):
        self.client.post(
            '/control/event/%s/%s/items/%s/down' % (self.orga1.slug, self.event1.slug, self.item1.id),
        )
        self.item1.refresh_from_db()
        self.item2.refresh_from_db()
        assert self.item1.position > self.item2.position
        self.client.post(
            '/control/event/%s/%s/items/%s/up' % (self.orga1.slug, self.event1.slug, self.item1.id),
        )
        self.item1.refresh_from_db()
        self.item2.refresh_from_db()
        assert self.item1.position < self.item2.position

    def test_create(self):
        self.client.post(
            '/control/event/%s/%s/items/add' % (self.orga1.slug, self.event1.slug),
            {'name_0': 'T-Shirt', 'default_price': '23.00', 'tax_rate': '19.00'},
        )
        resp = self.client.get('/control/event/%s/%s/items/' % (self.orga1.slug, self.event1.slug))
        assert 'T-Shirt' in resp.content.decode()

    def test_create_negative_price_rejected(self):
        self.client.post(
            '/control/event/%s/%s/items/add' % (self.orga1.slug, self.event1.slug),
            {'name_0': 'Invalid Item', 'default_price': '-500.00', 'tax_rate': '19.00'},
        )
        resp = self.client.get('/control/event/%s/%s/items/' % (self.orga1.slug, self.event1.slug))
        assert 'Invalid Item' not in resp.content.decode()

    def test_update(self):
        doc = self.get_doc('/control/event/%s/%s/items/%d/' % (self.orga1.slug, self.event1.slug, self.item2.id))
        d = extract_form_fields(doc.select('.container-fluid form')[0])
        d.update(
            {
                'name_0': 'Standard',
                'default_price': '23.00',
                'tax_rate': '19.00',
                'active': 'yes',
                'allow_cancel': 'yes',
                'sales_channels': 'web',
            }
        )
        self.client.post(
            '/control/event/%s/%s/items/%d/' % (self.orga1.slug, self.event1.slug, self.item1.id),
            d,
        )
        self.item1.refresh_from_db()
        assert self.item1.default_price == Decimal('23.00')

    def test_update_negative_price_rejected(self):
        old_price = self.item1.default_price
        doc = self.get_doc('/control/event/%s/%s/items/%d/' % (self.orga1.slug, self.event1.slug, self.item1.id))
        d = extract_form_fields(doc.select('.container-fluid form')[0])
        d.update(
            {
                'name_0': 'Standard',
                'default_price': '-500.00',
                'active': 'yes',
                'allow_cancel': 'yes',
                'sales_channels': 'web',
            }
        )
        self.client.post(
            '/control/event/%s/%s/items/%d/' % (self.orga1.slug, self.event1.slug, self.item1.id),
            d,
        )
        self.item1.refresh_from_db()
        assert self.item1.default_price == old_price

    def test_update_validate_giftcard(self):
        doc = self.get_doc('/control/event/%s/%s/items/%d/' % (self.orga1.slug, self.event1.slug, self.item2.id))
        d = extract_form_fields(doc.select('.container-fluid form')[0])
        d.update(
            {
                'name_0': 'Standard',
                'default_price': '23.00',
                'admission': 'on',
                'issue_giftcard': 'on',
                'active': 'yes',
                'allow_cancel': 'yes',
                'sales_channels': 'web',
            }
        )
        self.client.post(
            '/control/event/%s/%s/items/%d/' % (self.orga1.slug, self.event1.slug, self.item1.id),
            d,
        )
        self.item1.refresh_from_db()
        assert not self.item1.issue_giftcard

    def test_manipulate_addons(self):
        doc = self.get_doc('/control/event/%s/%s/items/%d/' % (self.orga1.slug, self.event1.slug, self.item2.id))
        d = extract_form_fields(doc.select('.container-fluid form')[0])

        d.update(
            {
                'addons-TOTAL_FORMS': '1',
                'addons-INITIAL_FORMS': '0',
                'addons-MIN_NUM_FORMS': '0',
                'addons-MAX_NUM_FORMS': '1000',
                'addons-0-id': '',
                'addons-0-addon_category': str(self.addoncat.pk),
                'addons-0-min_count': '1',
                'addons-0-max_count': '2',
            }
        )
        self.client.post(
            '/control/event/%s/%s/items/%d/' % (self.orga1.slug, self.event1.slug, self.item2.id),
            d,
        )
        with scopes_disabled():
            assert self.item2.addons.exists()
            assert self.item2.addons.first().addon_category == self.addoncat
            a = self.item2.addons.first()
        d.update(
            {
                'addons-TOTAL_FORMS': '1',
                'addons-INITIAL_FORMS': '1',
                'addons-MIN_NUM_FORMS': '0',
                'addons-MAX_NUM_FORMS': '1000',
                'addons-0-id': str(a.pk),
                'addons-0-addon_category': str(self.addoncat.pk),
                'addons-0-min_count': '1',
                'addons-0-max_count': '2',
                'addons-0-DELETE': 'on',
            }
        )
        self.client.post(
            '/control/event/%s/%s/items/%d/' % (self.orga1.slug, self.event1.slug, self.item2.id),
            d,
        )
        with scopes_disabled():
            assert not self.item2.addons.exists()

        # Do not allow duplicates
        d.update(
            {
                'addons-TOTAL_FORMS': '2',
                'addons-INITIAL_FORMS': '0',
                'addons-MIN_NUM_FORMS': '0',
                'addons-MAX_NUM_FORMS': '1000',
                'addons-0-id': '',
                'addons-0-addon_category': str(self.addoncat.pk),
                'addons-0-min_count': '1',
                'addons-0-max_count': '2',
                'addons-1-id': '',
                'addons-1-addon_category': str(self.addoncat.pk),
                'addons-1-min_count': '1',
                'addons-1-max_count': '2',
            }
        )
        self.client.post(
            '/control/event/%s/%s/items/%d/' % (self.orga1.slug, self.event1.slug, self.item2.id),
            d,
        )
        with scopes_disabled():
            assert self.item2.addons.count() == 1

    def test_manipulate_bundles(self):
        doc = self.get_doc('/control/event/%s/%s/items/%d/' % (self.orga1.slug, self.event1.slug, self.item2.id))
        d = extract_form_fields(doc.select('.container-fluid form')[0])

        d.update(
            {
                'bundles-TOTAL_FORMS': '1',
                'bundles-INITIAL_FORMS': '0',
                'bundles-MIN_NUM_FORMS': '0',
                'bundles-MAX_NUM_FORMS': '1000',
                'bundles-0-id': '',
                'bundles-0-itemvar': str(self.item1.pk),
                'bundles-0-count': '2',
                'bundles-0-designated_price': '',
            }
        )
        self.client.post(
            '/control/event/%s/%s/items/%d/' % (self.orga1.slug, self.event1.slug, self.item2.id),
            d,
        )
        with scopes_disabled():
            assert self.item2.bundles.exists()
            assert self.item2.bundles.first().bundled_item == self.item1
            assert self.item2.bundles.first().designated_price == Decimal('0.000')
        d.update(
            {
                'bundles-TOTAL_FORMS': '1',
                'bundles-INITIAL_FORMS': '1',
                'bundles-MIN_NUM_FORMS': '0',
                'bundles-MAX_NUM_FORMS': '1000',
                'bundles-0-id': str(self.item2.bundles.first().pk),
                'bundles-0-itemvar': str(self.item1.pk),
                'bundles-0-count': '2',
                'bundles-0-designated_price': '2.00',
                'bundles-0-DELETE': 'on',
            }
        )
        self.client.post(
            '/control/event/%s/%s/items/%d/' % (self.orga1.slug, self.event1.slug, self.item2.id),
            d,
        )
        with scopes_disabled():
            assert not self.item2.bundles.exists()

        # Do not allow self-reference
        d.update(
            {
                'bundles-TOTAL_FORMS': '1',
                'bundles-INITIAL_FORMS': '0',
                'bundles-MIN_NUM_FORMS': '0',
                'bundles-MAX_NUM_FORMS': '1000',
                'bundles-0-id': '',
                'bundles-0-itemvar': str(self.item2.pk),
                'bundles-0-count': '2',
                'bundles-0-designated_price': '2.00',
            }
        )
        self.client.post(
            '/control/event/%s/%s/items/%d/' % (self.orga1.slug, self.event1.slug, self.item2.id),
            d,
        )
        with scopes_disabled():
            assert not self.item2.bundles.exists()

        # Do not allow multi-level bundles
        with scopes_disabled():
            self.item1.bundles.create(bundled_item=self.item1, count=1, designated_price=0)
        d.update(
            {
                'bundles-TOTAL_FORMS': '1',
                'bundles-INITIAL_FORMS': '0',
                'bundles-MIN_NUM_FORMS': '0',
                'bundles-MAX_NUM_FORMS': '1000',
                'bundles-0-id': '',
                'bundles-0-itemvar': str(self.item1.pk),
                'bundles-0-count': '2',
                'bundles-0-designated_price': '2.00',
            }
        )
        self.client.post(
            '/control/event/%s/%s/items/%d/' % (self.orga1.slug, self.event1.slug, self.item2.id),
            d,
        )
        with scopes_disabled():
            assert not self.item2.bundles.exists()

    def test_update_variations(self):
        doc = self.get_doc('/control/event/%s/%s/items/%d/' % (self.orga1.slug, self.event1.slug, self.item2.id))
        d = extract_form_fields(doc.select('.container-fluid form')[0])
        d.update(
            {
                'variations-TOTAL_FORMS': '2',
                'variations-INITIAL_FORMS': '2',
                'variations-MIN_NUM_FORMS': '0',
                'variations-MAX_NUM_FORMS': '1000',
                'variations-0-id': str(self.var1.pk),
                'variations-0-value_0': 'Bronze',
                'variations-0-active': 'yes',
                'variations-1-id': str(self.var2.pk),
                'variations-1-value_0': 'Gold',
                'variations-1-active': 'yes',
            }
        )
        self.client.post(
            '/control/event/%s/%s/items/%d/' % (self.orga1.slug, self.event1.slug, self.item2.id),
            d,
        )
        self.var1.refresh_from_db()
        assert str(self.var1.value) == 'Bronze'

    def test_delete_variation(self):
        doc = self.get_doc('/control/event/%s/%s/items/%d/' % (self.orga1.slug, self.event1.slug, self.item2.id))
        d = extract_form_fields(doc.select('.container-fluid form')[0])
        d.update(
            {
                'variations-TOTAL_FORMS': '2',
                'variations-INITIAL_FORMS': '2',
                'variations-MIN_NUM_FORMS': '0',
                'variations-MAX_NUM_FORMS': '1000',
                'variations-0-id': str(self.var1.pk),
                'variations-0-value_0': 'Bronze',
                'variations-0-active': 'yes',
                'variations-1-id': str(self.var2.pk),
                'variations-1-value_0': 'Gold',
                'variations-1-active': 'yes',
                'variations-1-DELETE': 'yes',
            }
        )
        self.client.post(
            '/control/event/%s/%s/items/%d/' % (self.orga1.slug, self.event1.slug, self.item2.id),
            d,
        )
        with scopes_disabled():
            assert not self.item2.variations.filter(pk=self.var2.pk).exists()

    def test_delete(self):
        self.client.post(
            '/control/event/%s/%s/items/%d/delete' % (self.orga1.slug, self.event1.slug, self.item1.id),
            {},
        )
        with scopes_disabled():
            assert not self.event1.items.filter(pk=self.item1.pk).exists()
        self.client.post(
            '/control/event/%s/%s/items/%d/delete' % (self.orga1.slug, self.event1.slug, self.item2.id),
            {},
        )
        with scopes_disabled():
            assert not self.event1.items.filter(pk=self.item2.pk).exists()

    def test_delete_ordered(self):
        with scopes_disabled():
            o = Order.objects.create(
                code='FOO',
                event=self.event1,
                email='dummy@dummy.test',
                status=Order.STATUS_PENDING,
                datetime=now(),
                expires=now() + datetime.timedelta(days=10),
                total=14,
                locale='en',
            )
            OrderPosition.objects.create(
                order=o,
                item=self.item1,
                variation=None,
                price=Decimal('14'),
                attendee_name_parts={'full_name': 'Peter'},
            )
        self.client.post(
            '/control/event/%s/%s/items/%d/delete' % (self.orga1.slug, self.event1.slug, self.item1.id),
            {},
        )
        with scopes_disabled():
            assert self.event1.items.filter(pk=self.item1.pk).exists()
        self.item1.refresh_from_db()
        assert not self.item1.active

    def test_create_copy(self):
        with scopes_disabled():
            q = Question.objects.create(event=self.event1, question='Size', type='N')
            q.items.add(self.item2)
        self.item2.sales_channels = ['web', 'bar']

        self.client.post(
            '/control/event/%s/%s/items/add' % (self.orga1.slug, self.event1.slug),
            {
                'name_0': 'Intermediate',
                'default_price': '23.00',
                'tax_rate': '19.00',
                'copy_from': str(self.item2.pk),
                'has_variations': '1',
            },
        )
        with scopes_disabled():
            i_old = Item.objects.get(name__icontains='Business')
            i_new = Item.objects.get(name__icontains='Intermediate')
            assert i_new.category == i_old.category
            assert i_new.description == i_old.description
            assert i_new.active == i_old.active
            assert i_new.available_from == i_old.available_from
            assert i_new.available_until == i_old.available_until
            assert i_new.require_voucher == i_old.require_voucher
            assert i_new.hide_without_voucher == i_old.hide_without_voucher
            assert i_new.allow_cancel == i_old.allow_cancel
            assert i_new.sales_channels == i_old.sales_channels
            assert set(i_new.questions.all()) == set(i_old.questions.all())
            assert set([str(v.value) for v in i_new.variations.all()]) == set(
                [str(v.value) for v in i_old.variations.all()]
            )

    def test_add_to_existing_quota(self):
        with scopes_disabled():
            q = Quota.objects.create(event=self.event1, name='New Test Quota', size=50)

        doc = self.get_doc('/control/event/%s/%s/items/add' % (self.orga1.slug, self.event1.slug))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['name_0'] = 'Existing'
        form_data['default_price'] = '2.00'
        form_data['quota_option'] = 'existing'
        form_data['quota_add_existing'] = str(q.pk)
        doc = self.post_doc(
            '/control/event/%s/%s/items/add' % (self.orga1.slug, self.event1.slug),
            form_data,
        )

        with scopes_disabled():
            i = Item.objects.get(name__icontains='Existing')

            assert doc.select('.alert-success')
            assert q.items.filter(pk=i.pk).exists()

    def test_add_to_new_quota(self):
        doc = self.get_doc('/control/event/%s/%s/items/add' % (self.orga1.slug, self.event1.slug))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['name_0'] = 'New Item'
        form_data['default_price'] = '2.00'
        form_data['quota_option'] = 'new'
        form_data['quota_add_new_name'] = 'New Quota'
        form_data['quota_add_new_size'] = '200'
        doc = self.post_doc(
            '/control/event/%s/%s/items/add' % (self.orga1.slug, self.event1.slug),
            form_data,
        )

        assert doc.select('.alert-success')
        with scopes_disabled():
            assert Quota.objects.filter(name__icontains='New Quota').exists()
            assert Item.objects.filter(name__icontains='New Item').exists()
            i = Item.objects.get(name__icontains='New Item')
            q = Quota.objects.get(name__icontains='New Quota')
            assert q.items.filter(pk=i.pk).exists()

    def test_create_defaults_available_until(self):
        self.event1.date_to = datetime.datetime(2013, 12, 28, 18, 0, tzinfo=datetime.timezone.utc)
        self.event1.save()
        doc = self.get_doc('/control/event/%s/%s/items/add' % (self.orga1.slug, self.event1.slug))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['name_0'] = 'Timed ticket'
        form_data['default_price'] = '2.00'
        form_data['quota_option'] = 'none'
        doc = self.post_doc(
            '/control/event/%s/%s/items/add' % (self.orga1.slug, self.event1.slug),
            form_data,
        )
        assert doc.select('.alert-success')
        with scopes_disabled():
            item = Item.objects.get(name__icontains='Timed ticket')
            assert item.available_until == self.event1.date_to

    def test_order_forms_save_does_not_reset_common_settings(self):
        self.event1.settings.set('frontpage_text', LazyI18nString({'en': 'Presale intro text'}))
        self.event1.settings.set('primary_color', '#8fc93a')
        self.event1.settings.set('theme_color_success', '#157c02')
        self.event1.settings.set('theme_color_danger', '#d80000')
        self.event1.settings.set('theme_color_background', '#a0a0a0')
        self.event1.settings.set('hover_button_color', '#00826c')
        self.event1.settings.flush()

        doc = self.get_doc('/control/event/%s/%s/orderforms/' % (self.orga1.slug, self.event1.slug))
        form_data = extract_form_fields(doc.select('form')[0])
        assert 'settings-attendee_job_title_asked_required' in form_data

        doc = self.post_doc('/control/event/%s/%s/orderforms/' % (self.orga1.slug, self.event1.slug), form_data)
        assert doc.select('.alert-success')

        self.event1.settings.flush()
        assert self.event1.settings.get('primary_color') == '#8fc93a'
        assert self.event1.settings.get('theme_color_success') == '#157c02'
        assert self.event1.settings.get('theme_color_danger') == '#d80000'
        assert self.event1.settings.get('theme_color_background') == '#a0a0a0'
        assert self.event1.settings.get('hover_button_color') == '#00826c'

        frontpage_text = self.event1.settings.get('frontpage_text', as_type=LazyI18nString)
        assert frontpage_text.data.get('en') == 'Presale intro text'


class ProductDeleteTest(ItemFormTest):
    @override_settings(DEBUG=True)
    def test_delete_page_names_product(self):
        url = f'/control/event/{self.orga1.slug}/{self.event1.slug}/products/{self.item1.id}/delete'
        doc = self.get_doc(url)
        assert doc.select_one('form p strong').text == 'Standard'
        assert doc.select_one('button.btn-delete').text.strip() == 'Delete'

    @override_settings(DEBUG=True)
    def test_delete_page_offers_deactivation_for_ordered_product(self):
        with scope(organizer=self.orga1, event=self.event1):
            o = Order.objects.create(
                code='FOO',
                event=self.event1,
                email='dummy@dummy.test',
                status=Order.STATUS_PENDING,
                datetime=now(),
                expires=now() + datetime.timedelta(days=10),
                total=14,
                locale='en',
            )
            OrderPosition.objects.create(order=o, product=self.item1, variation=None, price=Decimal('14'))
        url = f'/control/event/{self.orga1.slug}/{self.event1.slug}/products/{self.item1.id}/delete'

        doc = self.get_doc(url)
        assert doc.select_one('form p strong').text == 'Standard'
        assert doc.select_one('button.btn-delete').text.strip() == 'Deactivate'

        self.item1.active = False
        self.item1.save()
        doc = self.get_doc(url)
        assert doc.select_one('p strong').text == 'Standard'
        assert doc.select_one('button.btn-delete') is None


@override_settings(SITE_URL='https://testserver')
class FreePriceBoundsTest(ItemFormTest):
    def test_clean_free_price_bounds_negative_min_standalone(self):
        with pytest.raises(forms.ValidationError) as excinfo:
            clean_free_price_bounds({
                'free_price': True,
                'default_price': Decimal('0.00'),
                'free_price_min': Decimal('-5.00'),
                'free_price_max': Decimal('20.00'),
            })
        assert 'free_price_min' in excinfo.value.message_dict
        assert 'The minimum price must not be negative.' in str(excinfo.value.message_dict['free_price_min'])

    def test_clean_free_price_bounds_negative_max_standalone(self):
        with pytest.raises(forms.ValidationError) as excinfo:
            clean_free_price_bounds({
                'free_price': True,
                'default_price': Decimal('0.00'),
                'free_price_min': Decimal('0.00'),
                'free_price_max': Decimal('-5.00'),
            })
        assert 'free_price_max' in excinfo.value.message_dict
        assert 'The maximum price must not be negative.' in str(excinfo.value.message_dict['free_price_max'])

    def test_clean_free_price_bounds_both_negative_standalone(self):
        with pytest.raises(forms.ValidationError) as excinfo:
            clean_free_price_bounds({
                'free_price': True,
                'default_price': Decimal('0.00'),
                'free_price_min': Decimal('-5.00'),
                'free_price_max': Decimal('-2.00'),
            })
        assert 'free_price_min' in excinfo.value.message_dict
        assert 'free_price_max' in excinfo.value.message_dict

    def test_clean_free_price_bounds_disabled_clears_negative(self):
        cleaned_data = {
            'free_price': False,
            'free_price_min': Decimal('-5.00'),
            'free_price_max': Decimal('-2.00'),
        }
        clean_free_price_bounds(cleaned_data)
        assert cleaned_data['free_price_min'] is None
        assert cleaned_data['free_price_max'] is None

    def test_clean_free_price_bounds_valid_values(self):
        cleaned_data = {
            'free_price': True,
            'default_price': Decimal('0.00'),
            'free_price_min': Decimal('5.00'),
            'free_price_max': Decimal('20.00'),
        }
        clean_free_price_bounds(cleaned_data)
        assert cleaned_data['free_price_min'] == Decimal('5.00')
        assert cleaned_data['free_price_max'] == Decimal('20.00')

    def test_create_item_negative_free_price_min_rejected(self):
        url = reverse('control:event.products.add', kwargs={'organizer': self.orga1.slug, 'event': self.event1.slug})
        doc = self.get_doc(url)
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['name_0'] = 'Free Price Donation'
        form_data['default_price'] = '0.00'
        form_data['free_price'] = 'on'
        form_data['free_price_min'] = '-5.00'
        form_data['free_price_max'] = '20.00'
        form_data['quota_option'] = 'none'
        doc = self.post_doc(url, form_data)
        assert not doc.select('.alert-success')
        assert doc.select('.has-error')
        min_field_group = doc.select('#id_free_price_min')[0].find_parent(class_='form-group')
        help_blocks = min_field_group.select('.help-block')
        assert len(help_blocks) == 1
        assert 'The minimum price must not be negative.' in help_blocks[0].text
        assert 'The minimum price a user has to enter' not in min_field_group.text
        with scopes_disabled():
            assert not Item.objects.filter(name__icontains='Free Price Donation').exists()

    def test_control_field_renderer_single_error_no_duplicate_help(self):
        """Test that ControlFieldRenderer renders only the validation error and hides help text on failure."""
        from eventyay.control.forms.renderers import ControlFieldRenderer

        class SampleForm(forms.Form):
            free_price_min = forms.DecimalField(
                label='Minimum price',
                help_text=(
                    'The minimum price a user has to enter. If left empty, '
                    'the default price will be used as the minimum.'
                ),
                required=False,
            )

        # Clean form without errors displays help text
        form = SampleForm()
        renderer = ControlFieldRenderer(form['free_price_min'])
        rendered = renderer.render()
        assert 'The minimum price a user has to enter' in rendered

        # Form with error displays only the single error message, hiding help text to avoid duplicate notifications
        form_err = SampleForm(data={'free_price_min': '-5.00'})
        form_err.is_valid()
        form_err.add_error('free_price_min', 'The minimum price must not be negative.')
        renderer_err = ControlFieldRenderer(form_err['free_price_min'])
        rendered_err = renderer_err.render()
        assert 'The minimum price must not be negative.' in rendered_err
        assert 'The minimum price a user has to enter' not in rendered_err

    def test_create_item_valid_free_price_succeeds(self):
        url = reverse('control:event.products.add', kwargs={'organizer': self.orga1.slug, 'event': self.event1.slug})
        doc = self.get_doc(url)
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['name_0'] = 'Valid Free Price'
        form_data['default_price'] = '0.00'
        form_data['free_price'] = 'on'
        form_data['free_price_min'] = '5.00'
        form_data['free_price_max'] = '20.00'
        form_data['quota_option'] = 'none'
        doc = self.post_doc(url, form_data)
        assert doc.select('.alert-success')
        with scopes_disabled():
            item = Item.objects.get(name__icontains='Valid Free Price')
            assert item.free_price is True
            assert item.free_price_min == Decimal('5.00')
            assert item.free_price_max == Decimal('20.00')

    def test_create_item_copy_from_negative_free_price_sanitized(self):
        with scopes_disabled():
            legacy_item = Item.objects.create(
                event=self.event1,
                name='Legacy Bad Product',
                default_price=Decimal('10.00'),
                free_price=True,
                free_price_min=Decimal('-5.00'),
                free_price_max=Decimal('20.00'),
            )
        url = reverse('control:event.products.add', kwargs={'organizer': self.orga1.slug, 'event': self.event1.slug})
        doc = self.get_doc(f'{url}?copy_from={legacy_item.pk}')
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['name_0'] = 'Cloned Product'
        form_data['copy_from'] = str(legacy_item.pk)
        form_data['quota_option'] = 'none'
        doc = self.post_doc(url, form_data)
        assert doc.select('.alert-success')
        with scopes_disabled():
            item = Item.objects.get(name__icontains='Cloned Product')
            assert item.free_price is True
            assert item.free_price_min is None
            assert item.free_price_max == Decimal('20.00')

    def test_product_create_form_save_sanitizes_copied_negative_bounds(self):
        with scopes_disabled():
            legacy_item = Item.objects.create(
                event=self.event1,
                name='Legacy Product Negative Bounds',
                default_price=Decimal('10.00'),
                free_price=True,
                free_price_min=Decimal('-5.00'),
                free_price_max=Decimal('-2.00'),
            )
            new_item = Item(event=self.event1)
            form = ProductCreateForm(
                instance=new_item,
                event=self.event1,
                user=self.user,
                data={
                    'name_0': 'Direct Cloned Product',
                    'default_price': '10.00',
                    'free_price': 'on',
                    'quota_option': 'none',
                    'copy_from': str(legacy_item.pk),
                },
            )
            assert form.is_valid()
            form.save()
            new_item.refresh_from_db()
            assert new_item.free_price is True
            assert new_item.free_price_min is None
            assert new_item.free_price_max is None

    def test_product_create_form_copy_from_preserves_user_entered_bounds(self):
        with scopes_disabled():
            source_item = Item.objects.create(
                event=self.event1,
                name='Source Item Bounds',
                default_price=Decimal('10.00'),
                free_price=True,
                free_price_min=Decimal('5.00'),
                free_price_max=Decimal('20.00'),
            )
            new_item = Item(event=self.event1)
            form = ProductCreateForm(
                instance=new_item,
                event=self.event1,
                user=self.user,
                data={
                    'name_0': 'Custom Bounds Product',
                    'default_price': '10.00',
                    'free_price': 'on',
                    'free_price_min': '8.00',
                    'free_price_max': '35.00',
                    'quota_option': 'none',
                    'copy_from': str(source_item.pk),
                },
            )
            assert form.is_valid()
            form.save()
            new_item.refresh_from_db()
            assert new_item.free_price is True
            assert new_item.free_price_min == Decimal('8.00')
            assert new_item.free_price_max == Decimal('35.00')

    def test_product_create_form_copy_from_preserves_disabled_free_price(self):
        with scopes_disabled():
            source_item = Item.objects.create(
                event=self.event1,
                name='Source Item Free Price Enabled',
                default_price=Decimal('10.00'),
                free_price=True,
                free_price_min=Decimal('5.00'),
                free_price_max=Decimal('20.00'),
            )
            new_item = Item(event=self.event1)
            form = ProductCreateForm(
                instance=new_item,
                event=self.event1,
                user=self.user,
                data={
                    'name_0': 'Disabled Free Price Product',
                    'default_price': '10.00',
                    'quota_option': 'none',
                    'copy_from': str(source_item.pk),
                },
            )
            assert form.is_valid()
            form.save()
            new_item.refresh_from_db()
            assert new_item.free_price is False
            assert new_item.free_price_min is None
            assert new_item.free_price_max is None

    def test_create_item_copy_from_exceeds_max_rejected(self):
        with scopes_disabled():
            source_item = Item.objects.create(
                event=self.event1,
                name='Source Product With Limits',
                default_price=Decimal('10.00'),
                free_price=True,
                free_price_min=Decimal('5.00'),
                free_price_max=Decimal('15.00'),
            )
            new_item = Item(event=self.event1)
            form = ProductCreateForm(
                instance=new_item,
                event=self.event1,
                user=self.user,
                data={
                    'name_0': 'Higher Default Price',
                    'default_price': '25.00',
                    'free_price': 'on',
                    'free_price_min': '5.00',
                    'free_price_max': '15.00',
                    'quota_option': 'none',
                    'copy_from': str(source_item.pk),
                },
            )
            assert not form.is_valid()
            assert 'copy_from' in form.errors
            copy_errors = str(form.errors['copy_from'])
            assert 'The selected product’s maximum price is lower than the entered default price.' in copy_errors
            assert 'configured minimum price' not in copy_errors

    def test_create_item_copy_from_source_min_exceeds_max_rejected(self):
        with scopes_disabled():
            legacy_item = Item.objects.create(
                event=self.event1,
                name='Legacy Inverted Bounds',
                default_price=Decimal('10.00'),
                free_price=True,
                free_price_min=Decimal('20.00'),
                free_price_max=Decimal('10.00'),
            )
            new_item = Item(event=self.event1)
            form = ProductCreateForm(
                instance=new_item,
                event=self.event1,
                user=self.user,
                data={
                    'name_0': 'Cloned Inverted',
                    'default_price': '5.00',
                    'free_price': 'on',
                    'free_price_min': '20.00',
                    'free_price_max': '10.00',
                    'quota_option': 'none',
                    'copy_from': str(legacy_item.pk),
                },
            )
            assert not form.is_valid()
            assert 'copy_from' in form.errors
            copy_errors = str(form.errors['copy_from'])
            assert 'The selected product’s maximum price is lower than its configured minimum price.' in copy_errors
            assert 'entered default price' not in copy_errors

    def test_create_item_copy_from_both_exceed_max_rejected(self):
        with scopes_disabled():
            legacy_item = Item.objects.create(
                event=self.event1,
                name='Legacy Both Inverted',
                default_price=Decimal('10.00'),
                free_price=True,
                free_price_min=Decimal('20.00'),
                free_price_max=Decimal('10.00'),
            )
            new_item = Item(event=self.event1)
            form = ProductCreateForm(
                instance=new_item,
                event=self.event1,
                user=self.user,
                data={
                    'name_0': 'Cloned Both Conflicts',
                    'default_price': '25.00',
                    'free_price': 'on',
                    'free_price_min': '20.00',
                    'free_price_max': '10.00',
                    'quota_option': 'none',
                    'copy_from': str(legacy_item.pk),
                },
            )
            assert not form.is_valid()
            assert 'copy_from' in form.errors
            copy_errors = str(form.errors['copy_from'])
            assert 'The selected product’s maximum price is lower than the entered default price.' in copy_errors
            assert 'The selected product’s maximum price is lower than its configured minimum price.' in copy_errors

    def test_product_create_form_save_commit_false_preserves_unsaved_state(self):
        """Test ProductCreateForm.save(commit=False) sets copied bounds on the instance without saving to database."""
        with scopes_disabled():
            legacy_item = Item.objects.create(
                event=self.event1,
                name='Legacy Product Bounds',
                default_price=Decimal('10.00'),
                free_price=True,
                free_price_min=Decimal('5.00'),
                free_price_max=Decimal('20.00'),
            )
            new_item = Item(event=self.event1)
            form = ProductCreateForm(
                instance=new_item,
                event=self.event1,
                user=self.user,
                data={
                    'name_0': 'Unsaved Product',
                    'default_price': '10.00',
                    'free_price': 'on',
                    'free_price_min': '5.00',
                    'free_price_max': '20.00',
                    'quota_option': 'none',
                    'copy_from': str(legacy_item.pk),
                },
            )
            assert form.is_valid()
            instance = form.save(commit=False)
            assert instance.pk is None
            assert instance.free_price is True
            assert instance.free_price_min == Decimal('5.00')
            assert instance.free_price_max == Decimal('20.00')

    def test_product_create_form_init_populates_free_price_initial_from_source(self):
        """Test ProductCreateForm.__init__ populates self.initial for FREE_PRICE_FIELDS
        and changed_data detects unchecking.
        """
        with scopes_disabled():
            source_item = Item.objects.create(
                event=self.event1,
                name='Source Item For Init',
                default_price=Decimal('10.00'),
                free_price=True,
                free_price_min=Decimal('5.00'),
                free_price_max=Decimal('20.00'),
            )
            # Unbound form (e.g. GET request with copy_from in initial)
            unbound_form = ProductCreateForm(
                event=self.event1,
                user=self.user,
                initial={'copy_from': source_item},
            )
            assert unbound_form.initial['free_price'] is True
            assert unbound_form.initial['free_price_min'] == Decimal('5.00')
            assert unbound_form.initial['free_price_max'] == Decimal('20.00')

            # Bound form (POST request where user leaves free_price unchecked)
            new_item = Item(event=self.event1)
            bound_form = ProductCreateForm(
                instance=new_item,
                event=self.event1,
                user=self.user,
                data={
                    'name_0': 'Unchecked Copy',
                    'default_price': '10.00',
                    'quota_option': 'none',
                    'copy_from': str(source_item.pk),
                },
            )
            assert bound_form.initial['free_price'] is True
            assert bound_form.is_valid()
            assert 'free_price' in bound_form.changed_data
            saved_item = bound_form.save()
            assert saved_item.free_price is False
            assert saved_item.free_price_min is None
            assert saved_item.free_price_max is None


