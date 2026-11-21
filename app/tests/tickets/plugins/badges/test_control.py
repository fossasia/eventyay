import datetime
import json
import shutil
import subprocess

from django.contrib.staticfiles import finders
from django.test import override_settings
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Product as Item, Organizer, Team, User
from eventyay.plugins.badges.models import BadgeProduct as BadgeItem
from tests.tickets.base import SoupTest, extract_form_fields


@override_settings(SITE_URL='https://testserver')
class BadgeLayoutFormTest(SoupTest):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user('dummy@dummy.dummy', 'dummy')
        self.orga1 = Organizer.objects.create(name='CCC', slug='ccc')
        self.orga2 = Organizer.objects.create(name='MRM', slug='mrm')
        self.event1 = Event.objects.create(
            organizer=self.orga1,
            name='30C3',
            slug='30c3',
            plugins='eventyay.plugins.badges',
            date_from=datetime.datetime(2013, 12, 26, tzinfo=datetime.timezone.utc),
        )
        self.item1 = Item.objects.create(event=self.event1, name='Standard', default_price=0, position=1)
        t = Team.objects.create(
            organizer=self.orga1,
            can_change_event_settings=True,
            can_view_orders=True,
            can_change_items=True,
            all_events=True,
            can_create_events=True,
            can_change_orders=True,
            can_change_vouchers=True,
        )
        t.members.add(self.user)
        t.limit_events.add(self.event1)
        self.client.login(email='dummy@dummy.dummy', password='dummy')

    def test_create(self):
        doc = self.get_doc('/control/event/%s/%s/badges/add' % (self.orga1.slug, self.event1.slug))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['name'] = 'Layout 1'
        doc = self.post_doc(
            '/control/event/%s/%s/badges/add' % (self.orga1.slug, self.event1.slug),
            form_data,
        )
        assert doc.select('.alert-success')
        self.assertIn('Layout 1', doc.select('#page-wrapper')[0].text)
        assert self.event1.badge_layouts.get(default=True, name='Layout 1')

    def test_set_default(self):
        with scopes_disabled():
            bl1 = self.event1.badge_layouts.create(name='Layout 1', default=True)
            bl2 = self.event1.badge_layouts.create(name='Layout 2')
        self.post_doc(
            '/control/event/%s/%s/badges/%s/default' % (self.orga1.slug, self.event1.slug, bl2.id),
            {},
        )
        bl1.refresh_from_db()
        assert not bl1.default
        bl2.refresh_from_db()
        assert bl2.default

    def test_delete(self):
        with scopes_disabled():
            bl1 = self.event1.badge_layouts.create(name='Layout 1', default=True)
            bl2 = self.event1.badge_layouts.create(name='Layout 2')
        doc = self.get_doc('/control/event/%s/%s/badges/%s/delete' % (self.orga1.slug, self.event1.slug, bl1.id))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        doc = self.post_doc(
            '/control/event/%s/%s/badges/%s/delete' % (self.orga1.slug, self.event1.slug, bl1.id),
            form_data,
        )
        assert doc.select('.alert-success')
        self.assertNotIn('Layout 1', doc.select('#page-wrapper')[0].text)
        with scopes_disabled():
            assert self.event1.badge_layouts.count() == 1
        bl2.refresh_from_db()
        assert bl2.default

    def test_set_on_item(self):
        with scopes_disabled():
            self.event1.badge_layouts.create(name='Layout 1', default=True)
            bl2 = self.event1.badge_layouts.create(name='Layout 2')
        doc = self.get_doc('/control/event/%s/%s/items/%d/' % (self.orga1.slug, self.event1.slug, self.item1.id))
        d = extract_form_fields(doc.select('.container-fluid form')[0])
        d.update(
            {
                'name_0': 'Standard',
                'default_price': '23.00',
                'tax_rate': '19.00',
                'active': 'yes',
                'allow_cancel': 'yes',
                'badgeitem-layout': bl2.pk,
                'sales_channels': 'web',
            }
        )
        self.client.post(
            '/control/event/%s/%s/items/%d/' % (self.orga1.slug, self.event1.slug, self.item1.id),
            d,
        )
        with scopes_disabled():
            assert BadgeItem.objects.get(item=self.item1, layout=bl2)
        doc = self.get_doc('/control/event/%s/%s/items/%d/' % (self.orga1.slug, self.event1.slug, self.item1.id))
        d = extract_form_fields(doc.select('.container-fluid form')[0])
        d.update(
            {
                'name_0': 'Standard',
                'default_price': '23.00',
                'tax_rate': '19.00',
                'active': 'yes',
                'allow_cancel': 'yes',
                'sales_channels': 'web',
                'badgeitem-layout': '',
            }
        )
        self.client.post(
            '/control/event/%s/%s/items/%d/' % (self.orga1.slug, self.event1.slug, self.item1.id),
            d,
        )
        with scopes_disabled():
            assert not BadgeItem.objects.filter(item=self.item1, layout=bl2).exists()

    def test_item_copy(self):
        with scopes_disabled():
            bl2 = self.event1.badge_layouts.create(name='Layout 2')
            BadgeItem.objects.create(item=self.item1, layout=bl2)

        self.client.post(
            '/control/event/%s/%s/items/add' % (self.orga1.slug, self.event1.slug),
            {
                'name_0': 'Intermediate',
                'default_price': '23.00',
                'tax_rate': '19.00',
                'copy_from': str(self.item1.pk),
                'has_variations': '1',
            },
        )
        with scopes_disabled():
            i_new = Item.objects.get(name__icontains='Intermediate')
            assert BadgeItem.objects.get(item=i_new, layout=bl2)
            assert BadgeItem.objects.get(item=self.item1, layout=bl2)

    def test_copy_event(self):
        with scopes_disabled():
            bl2 = self.event1.badge_layouts.create(name='Layout 2')
            BadgeItem.objects.create(item=self.item1, layout=bl2)
        self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'foundation',
                'event_wizard-prefix': 'event_wizard',
                'foundation-organizer': self.orga1.pk,
                'foundation-locales': ('en',),
            },
        )
        self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'basics',
                'event_wizard-prefix': 'event_wizard',
                'basics-name_0': '33C3',
                'basics-slug': '33c3',
                'basics-date_from_0': '2016-12-27',
                'basics-date_from_1': '10:00:00',
                'basics-date_to_0': '2016-12-30',
                'basics-date_to_1': '19:00:00',
                'basics-location_0': 'Hamburg',
                'basics-currency': 'EUR',
                'basics-tax_rate': '19.00',
                'basics-locale': 'en',
                'basics-timezone': 'Europe/Berlin',
            },
        )
        self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'copy',
                'event_wizard-prefix': 'event_wizard',
                'copy-copy_from_event': self.event1.pk,
            },
        )

        with scopes_disabled():
            ev = Event.objects.get(slug='33c3')
            i_new = ev.items.first()
            bl_new = ev.badge_layouts.first()
            assert BadgeItem.objects.get(item=i_new, layout=bl_new)

    def test_editor_exposes_multi_object_align_controls(self):
        with scopes_disabled():
            layout = self.event1.badge_layouts.create(name='Layout 1', default=True)
        doc = self.get_doc(
            '/control/event/%s/%s/badges/%s/editor' % (self.orga1.slug, self.event1.slug, layout.id)
        )
        align = doc.select_one('#toolbox-object-align')
        assert align is not None
        for edge in ('left', 'center', 'right', 'top', 'middle', 'bottom'):
            assert align.select_one('button[data-align=%s]' % edge) is not None
        assert 'Shift-click' in doc.select_one('#toolbox').text

    def test_editor_exposes_pin_and_group_text_controls(self):
        with scopes_disabled():
            layout = self.event1.badge_layouts.create(name='Layout 1', default=True)
        doc = self.get_doc(
            '/control/event/%s/%s/badges/%s/editor' % (self.orga1.slug, self.event1.slug, layout.id)
        )
        pin_btn = doc.select_one('#toolbox-pin')
        assert pin_btn is not None
        assert pin_btn.select_one('.fa-thumb-tack') is not None
        assert doc.select_one('.text-format #toolbox-fontsize') is not None
        assert doc.select_one('.text-format #toolbox-col') is not None
        assert doc.select_one('.text-individual #toolbox-content') is not None

        css_path = finders.find('pretixcontrol/scss/pdfeditor.css')
        assert css_path is not None
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()
        assert '#toolbox[data-type=group].group-all-text .text-format' in css_content
        assert '#toolbox[data-type=group] .text-individual' in css_content
        assert '#toolbox-pin.active' in css_content

    def test_editor_save_persists_pinned_state(self):
        js_path = finders.find('pretixcontrol/js/ui/editor.js')
        assert js_path is not None
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()
        assert 'pinned: !!o.pinned' in js_content
        assert 'editor._set_object_pinned(o, true)' in js_content

        with scopes_disabled():
            layout = self.event1.badge_layouts.create(name='Layout 1', default=True)
        posted_data = [
            {
                'type': 'textarea',
                'left': '10.00',
                'bottom': '20.00',
                'fontsize': '16.0',
                'color': [0, 0, 0],
                'fontfamily': 'Open Sans',
                'bold': False,
                'italic': False,
                'width': '50.00',
                'downward': False,
                'autofit_width': False,
                'content': 'event_name',
                'text': 'Sample Event',
                'rotation': 0,
                'align': 'left',
                'pinned': True,
            }
        ]
        resp = self.client.post(
            '/control/event/%s/%s/badges/%s/editor' % (self.orga1.slug, self.event1.slug, layout.id),
            {'data': json.dumps(posted_data)},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            follow=True,
        )
        assert resp.status_code == 200
        assert resp.json().get('status') == 'ok'
        with scopes_disabled():
            layout.refresh_from_db()
            saved_layout = json.loads(layout.layout)
            assert len(saved_layout) == 1
            assert saved_layout[0].get('pinned') is True

    def test_editor_save_dirty_tracking_contract(self):
        js_path = finders.find('pretixcontrol/js/ui/editor.js')
        assert js_path is not None
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()
        assert 'change_version: 0' in js_content
        assert 'editor.change_version += 1' in js_content
        assert 'editor.change_version === savedVersion' in js_content
        assert 'editor.dirty = true;' in js_content

        node_bin = shutil.which('node')
        if node_bin:
            js_script = """
            const fs = require('fs');
            const vm = require('vm');

            const jsPath = process.argv[1];
            const code = fs.readFileSync(jsPath, 'utf8');

            let pendingPost = null;
            const values = {
                '#toolbox-content': 'other',
                '#toolbox-content-other': 'sample',
                '#toolbox-fontsize': '12',
                '#toolbox-col': '#000000',
                '#toolbox-position-x': '10',
                '#toolbox-position-y': '10',
                '#toolbox-textwidth': '50',
            };

            const dummyJQuery = function(selector) {
                const obj = {
                    bind: () => obj,
                    on: () => obj,
                    get: () => ({}),
                    find: () => obj,
                    filter: () => obj,
                    first: () => obj,
                    each: () => obj,
                    attr: () => '',
                    val: (newVal) => {
                        if (typeof newVal !== 'undefined') {
                            values[selector] = newVal;
                            return obj;
                        }
                        return values[selector] !== undefined ? values[selector] : '';
                    },
                    prop: () => obj,
                    is: () => false,
                    hasClass: () => false,
                    addClass: () => obj,
                    removeClass: () => obj,
                    toggleClass: () => obj,
                    parent: () => obj,
                    siblings: () => obj,
                    closest: () => obj,
                    remove: () => obj,
                    html: () => obj,
                    text: () => 'Save',
                    data: () => null,
                    removeData: () => obj,
                    modal: () => obj,
                    toggle: () => obj,
                    prepend: () => obj,
                    length: 0,
                };
                return obj;
            };
            dummyJQuery.post = (url, payload, cb) => {
                pendingPost = cb;
                return { fail: () => {} };
            };
            dummyJQuery.trim = (s) => (s ? s.trim() : '');

            const mockTextObj = {
                type: 'text',
                content: 'other',
                placeholder_text: 'sample',
                text: 'sample',
                fontSize: 12 * 1.33,
                maxFontPt: 12,
                width: 50,
                height: 20,
                scaleX: 1,
                scaleY: 1,
                set: function(k, v) { this[k] = v; },
                setCoords: () => {},
                rotate: () => {},
            };

            const sandbox = {
                $: dummyJQuery,
                jQuery: dummyJQuery,
                gettext: (s) => s,
                fabric: {
                    util: {
                        createClass: function(parent, def) {
                            function Cls() {}
                            Cls.prototype = Object.create(parent ? parent.prototype : {});
                            Object.assign(Cls.prototype, def);
                            return Cls;
                        },
                        object: { extend: Object.assign }
                    },
                    Image: function() {},
                    Rect: function() {},
                    Object: { _fromObject: () => {} },
                    Color: function() { return { _source: [0, 0, 0] }; }
                },
                PDFJS: {},
                FormData: function() { this.append = () => {}; },
                fetch: () => Promise.resolve({ ok: true, blob: () => Promise.resolve({}) }),
                window: { location: { href: 'http://test' }, setTimeout: () => {} },
                setTimeout: () => {},
                clearTimeout: () => {},
                alert: () => {},
                document: {
                    getElementById: () => null,
                    querySelector: () => null,
                    querySelectorAll: () => [],
                    activeElement: null,
                    createElement: () => ({
                        getContext: () => ({
                            measureText: () => ({ width: 10 })
                        })
                    })
                },
                console: console
            };
            vm.createContext(sandbox);
            vm.runInContext(code, sandbox);

            const editor = sandbox.editor;
            editor.fabric = {
                getActiveObjects: () => [mockTextObj],
                renderAll: () => {},
                discardActiveObject: () => {},
            };
            editor.pdf_viewport = { width: 500, height: 700 };
            editor._get_active_object = () => mockTextObj;
            editor._get_toolbox_target_object = () => mockTextObj;
            editor._is_active_selection = () => false;
            editor.dump = () => [];
            editor._csrf_token = () => 'token';
            editor._pt2px = (pt) => pt * 1.33;
            editor._mm2px = (mm) => mm * 3.78;
            editor._px2mm = (px) => px / 3.78;
            editor._update_toolbox_values = () => {};
            editor._show_preview_blob = () => {};

            // 1. Verify preview on unchanged text leaves dirty false and change_version intact
            editor.dirty = false;
            editor.change_version = 1;
            editor._preview({ preventDefault: () => {} });
            if (editor.dirty !== false || editor.change_version !== 1) {
                throw new Error('Preview on unchanged text marked editor dirty');
            }

            // 2. Start save while dirty (in-flight version = 1)
            editor.dirty = true;
            editor._save();
            if (!pendingPost) throw new Error('Expected $.post to be called');
            const inFlightCb1 = pendingPost;
            pendingPost = null;

            // 3. While save is pending, user edits a toolbox field
            editor._update_values_from_toolbox();
            if (editor.change_version !== 2) throw new Error('Expected change_version to increment to 2, got ' + editor.change_version);
            if (!editor.dirty) throw new Error('Expected dirty to be true');

            // 4. Complete the in-flight save request (for version 1)
            inFlightCb1({ status: 'ok' });
            if (editor.dirty !== true) throw new Error('Regression failure: dirty should remain true after in-flight edit!');

            // 5. Control case: save completes when no edits happen concurrently
            editor._save();
            if (!pendingPost) throw new Error('Expected $.post to be called');
            const inFlightCb2 = pendingPost;
            inFlightCb2({ status: 'ok' });
            if (editor.dirty !== false) throw new Error('Control failure: dirty should be cleared when no edits occurred!');

            console.log('OK');
            process.exit(0);
            """
            res = subprocess.run([node_bin, '-e', js_script, js_path], capture_output=True, text=True)
            assert res.returncode == 0
            assert 'OK' in res.stdout
