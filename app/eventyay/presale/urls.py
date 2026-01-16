from django.urls import include, path, re_path
from django.views.decorators.csrf import csrf_exempt

import eventyay.presale.views.cart
import eventyay.presale.views.checkout
import eventyay.presale.views.event
import eventyay.presale.views.locale
import eventyay.presale.views.order
import eventyay.presale.views.organizer
import eventyay.presale.views.robots
import eventyay.presale.views.theme
import eventyay.presale.views.user
import eventyay.presale.views.waiting
import eventyay.presale.views.widget
from eventyay.common.urls import OrganizerSlugConverter  # noqa: F401 (registers converter)

# This is not a valid Django URL configuration, as the final
# configuration is done by the eventyay.multidomain package.
frame_wrapped_urls = [
    path(
        'cart/remove',
        eventyay.presale.views.cart.CartRemove.as_view(),
        name='event.cart.remove',
    ),
    path(
        'cart/voucher',
        eventyay.presale.views.cart.CartApplyVoucher.as_view(),
        name='event.cart.voucher',
    ),
    path(
        'cart/clear',
        eventyay.presale.views.cart.CartClear.as_view(),
        name='event.cart.clear',
    ),
    path(
        'cart/answer/<answer>/',
        eventyay.presale.views.cart.AnswerDownload.as_view(),
        name='event.cart.download.answer',
    ),
    path(
        'checkout/start',
        eventyay.presale.views.checkout.CheckoutView.as_view(),
        name='event.checkout.start',
    ),
    path(
        'checkout/<step>/',
        eventyay.presale.views.checkout.CheckoutView.as_view(),
        name='event.checkout',
    ),
    path(
        'redeem/',
        eventyay.presale.views.cart.RedeemView.as_view(),
        name='event.redeem',
    ),
    path(
        'online-video/join',
        eventyay.presale.views.event.JoinOnlineVideoView.as_view(),
        name='event.onlinevideo.join',
    ),
    path(
        'seatingframe/',
        eventyay.presale.views.event.SeatingPlanView.as_view(),
        name='event.seatingplan',
    ),
    path(
        '<int:subevent>/seatingframe/',
        eventyay.presale.views.event.SeatingPlanView.as_view(),
        name='event.seatingplan',
    ),
    path(
        '<int:subevent>/',
        eventyay.presale.views.event.EventIndex.as_view(),
        name='event.index',
    ),
    path(
        'waitinglist',
        eventyay.presale.views.waiting.WaitingView.as_view(),
        name='event.waitinglist',
    ),
    path(
        'tickets/',
        eventyay.presale.views.event.EventIndex.as_view(),
        name='event.tickets',
    ),
    path('', eventyay.presale.views.event.EventIndex.as_view(), name='event.index'),
]
event_patterns = [
    # Cart/checkout patterns are a bit more complicated, as they should have simple URLs like cart/clear in normal
    # cases, but need to have versions with unguessable URLs like w/8l4Y83XNonjLxoBb/cart/clear to be used in widget
    # mode. This is required to prevent all clickjacking and CSRF attacks that would otherwise be possible.
    # First, we define the normal version. The docstring of get_or_create_cart_id() has more information on this.
    path('', include(frame_wrapped_urls)),
    # Second, the widget version
    re_path(r'w/(?P<cart_namespace>[a-zA-Z0-9]{16})/', include(frame_wrapped_urls)),
    # Third, a fake version that is defined like the first (and never gets called), but makes reversing URLs easier
    re_path(r'(?P<cart_namespace>[_]{0})', include(frame_wrapped_urls)),
    # CartAdd goes extra since it also gets a csrf_exempt decorator in one of the cases
    re_path(
        r'^cart/add$',
        eventyay.presale.views.cart.CartAdd.as_view(),
        name='event.cart.add',
    ),
    re_path(
        r'^(?P<cart_namespace>[_]{0})cart/add$',
        eventyay.presale.views.cart.CartAdd.as_view(),
        name='event.cart.add',
    ),
    re_path(
        r'w/(?P<cart_namespace>[a-zA-Z0-9]{16})/cart/add',
        csrf_exempt(eventyay.presale.views.cart.CartAdd.as_view()),
        name='event.cart.add',
    ),
    re_path(
        r'unlock/(?P<hash>[a-z0-9]{64})/$',
        eventyay.presale.views.user.UnlockHashView.as_view(),
        name='event.payment.unlock',
    ),
    path(
        'resend/',
        eventyay.presale.views.user.ResendLinkView.as_view(),
        name='event.resend_link',
    ),
    re_path(
        r'^order/(?P<order>[^/]+)/(?P<secret>[A-Za-z0-9]+)/open/(?P<hash>[a-z0-9]+)/$',
        eventyay.presale.views.order.OrderOpen.as_view(),
        name='event.order.open',
    ),
    re_path(
        r'^order/(?P<order>[^/]+)/(?P<secret>[A-Za-z0-9]+)/$',
        eventyay.presale.views.order.OrderDetails.as_view(),
        name='event.order',
    ),
    re_path(
        r'^order/(?P<order>[^/]+)/(?P<secret>[A-Za-z0-9]+)/invoice$',
        eventyay.presale.views.order.OrderInvoiceCreate.as_view(),
        name='event.order.geninvoice',
    ),
    re_path(
        r'^order/(?P<order>[^/]+)/(?P<secret>[A-Za-z0-9]+)/change$',
        eventyay.presale.views.order.OrderChange.as_view(),
        name='event.order.change',
    ),
    re_path(
        r'^order/(?P<order>[^/]+)/(?P<secret>[A-Za-z0-9]+)/cancel$',
        eventyay.presale.views.order.OrderCancel.as_view(),
        name='event.order.cancel',
    ),
    re_path(
        r'^order/(?P<order>[^/]+)/(?P<secret>[A-Za-z0-9]+)/cancel/do$',
        eventyay.presale.views.order.OrderCancelDo.as_view(),
        name='event.order.cancel.do',
    ),
    re_path(
        r'^order/(?P<order>[^/]+)/(?P<secret>[A-Za-z0-9]+)/modify$',
        eventyay.presale.views.order.OrderModify.as_view(),
        name='event.order.modify',
    ),
    re_path(
        r'^order/(?P<order>[^/]+)/(?P<secret>[A-Za-z0-9]+)/pay/(?P<payment>[0-9]+)/$',
        eventyay.presale.views.order.OrderPaymentStart.as_view(),
        name='event.order.pay',
    ),
    re_path(
        r'^order/(?P<order>[^/]+)/(?P<secret>[A-Za-z0-9]+)/pay/(?P<payment>[0-9]+)/confirm$',
        eventyay.presale.views.order.OrderPaymentConfirm.as_view(),
        name='event.order.pay.confirm',
    ),
    re_path(
        r'^order/(?P<order>[^/]+)/(?P<secret>[A-Za-z0-9]+)/pay/(?P<payment>[0-9]+)/complete$',
        eventyay.presale.views.order.OrderPaymentComplete.as_view(),
        name='event.order.pay.complete',
    ),
    re_path(
        r'^order/(?P<order>[^/]+)/(?P<secret>[A-Za-z0-9]+)/pay/change',
        eventyay.presale.views.order.OrderPayChangeMethod.as_view(),
        name='event.order.pay.change',
    ),
    re_path(
        r'^order/(?P<order>[^/]+)/(?P<secret>[A-Za-z0-9]+)/answer/(?P<answer>[^/]+)/$',
        eventyay.presale.views.order.AnswerDownload.as_view(),
        name='event.order.download.answer',
    ),
    re_path(
        r'^order/(?P<order>[^/]+)/(?P<secret>[A-Za-z0-9]+)/download/(?P<output>[^/]+)$',
        eventyay.presale.views.order.OrderDownload.as_view(),
        name='event.order.download.combined',
    ),
    re_path(
        r'^order/(?P<order>[^/]+)/(?P<secret>[A-Za-z0-9]+)/download/(?P<position>[0-9]+)/(?P<output>[^/]+)$',
        eventyay.presale.views.order.OrderDownload.as_view(),
        name='event.order.download',
    ),
    re_path(
        r'^order/(?P<order>[^/]+)/(?P<secret>[A-Za-z0-9]+)/invoice/(?P<invoice>[0-9]+)$',
        eventyay.presale.views.order.InvoiceDownload.as_view(),
        name='event.invoice.download',
    ),
    re_path(
        r'^ticket/(?P<order>[^/]+)/(?P<position>\d+)/(?P<secret>[A-Za-z0-9]+)/$',
        eventyay.presale.views.order.OrderPositionDetails.as_view(),
        name='event.order.position',
    ),
    re_path(
        r'^ticket/(?P<order>[^/]+)/(?P<position>\d+)/(?P<secret>[A-Za-z0-9]+)/(?P<view_schedule>True|False)/venueless/$',
        eventyay.presale.views.order.OrderPositionJoin.as_view(),
        name='event.venueless.join',
    ),
    re_path(
        r'^ticket/(?P<order>[^/]+)/(?P<position>\d+)/(?P<secret>[A-Za-z0-9]+)/download/(?P<pid>[0-9]+)/(?P<output>[^/]+)$',
        eventyay.presale.views.order.OrderPositionDownload.as_view(),
        name='event.order.position.download',
    ),
    path(
        'ical/',
        eventyay.presale.views.event.EventIcalDownload.as_view(),
        name='event.ical.download',
    ),
    path(
        'ical/<int:subevent>/',
        eventyay.presale.views.event.EventIcalDownload.as_view(),
        name='event.ical.download',
    ),
    path('auth/', eventyay.presale.views.event.EventAuth.as_view(), name='event.auth'),
    path(
        'widget/product_list',
        eventyay.presale.views.widget.WidgetAPIProductList.as_view(),
        name='event.widget.productlist',
    ),
    path(
        'widget/v1.css',
        eventyay.presale.views.widget.widget_css,
        name='event.widget.css',
    ),
    path(
        '<int:subevent>/widget/product_list',
        eventyay.presale.views.widget.WidgetAPIProductList.as_view(),
        name='event.widget.productlist',
    ),
]

organizer_patterns = [
    path(
        '',
        eventyay.presale.views.organizer.OrganizerIndex.as_view(),
        name='organizer.index',
    ),
    path(
        'events/ical/',
        eventyay.presale.views.organizer.OrganizerIcalDownload.as_view(),
        name='organizer.ical',
    ),
    path(
        'widget/product_list',
        eventyay.presale.views.widget.WidgetAPIProductList.as_view(),
        name='organizer.widget.productlist',
    ),
    path(
        'widget/v1.css',
        eventyay.presale.views.widget.widget_css,
        name='organizer.widget.css',
    ),
]

locale_patterns = [
    path(
        'locale/set',
        eventyay.presale.views.locale.LocaleSet.as_view(),
        name='locale.set',
    ),
    path(
        'locale/event',
        eventyay.presale.views.locale.EventLocaleSet.as_view(),
        name='locale.event',
    ),
    path('robots.txt', eventyay.presale.views.robots.robots_txt, name='robots.txt'),
    path(
        'browserconfig.xml',
        eventyay.presale.views.theme.browserconfig_xml,
        name='browserconfig.xml',
    ),
    path(
        'site.webmanifest',
        eventyay.presale.views.theme.webmanifest,
        name='site.webmanifest',
    ),
    path(
        'widget/v1.<slug:lang>.js',
        eventyay.presale.views.widget.widget_js,
        name='widget.js',
    ),
]
