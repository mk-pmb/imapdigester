import sys
from unittest import TestCase
import unittest
import os

from importlib import reload
from mock import Mock, call
from mockextras import stub

sys.path = [os.path.abspath(os.path.join('..', os.pardir))] + sys.path
from digesters.confluence.confluence_notification_digester import ConfluenceNotificationDigester
from digesters.digestion_processor import DigestionProcessor

MAIL_HDR = """From: \"Apache Confluence\" <ph@example.com>
Content-Transfer-Encoding: 8bit
Content-Type: multipart/alternative; boundary="---NOTIFICATION_BOUNDARY-5678"
MIME-Version: 1.0
This is a multi-part message in MIME format.
-----NOTIFICATION_BOUNDARY-5678
Content-Type: text/html; charset="utf-8"
Content-Transfer-Encoding: 8bit


"""


class NotificationsStore(object):

    def __init__(self, cls=object):
        self._cls = cls
        self.notifications = None

    def __eq__(self, other):
        self.notifications = other
        return True

    def __ne__(self, other):
        return False

    def __repr__(self):
        return "NotificationsStore(..)"


class TestConfluenceNotifications(TestCase):

    def __init__(self, methodName='runTest'):
        super(TestConfluenceNotifications, self).__init__(methodName)
        reload(sys)
        # sys.setdefaultencoding('utf8')

    def test_two_related_notifications_can_be_rolled_up(self):

        expected_payload = """<html><body><span>You have previously read notifications up to: Apr 09 2016 02:37 AM</span>
<table>
  <tr style="background-color: #acf;">
    <th>Notifications</th>
  </tr>
          <tr style="">
    <td>
      What: Noble Paul edited a page<br/>
      Space: solr:<br/>
      Page: <a href="https://cwiki.apache.org/confluence/display/solr/Config+API">Config API</a><br/>
      Excerpt: Page nodes added: 4, removed: 0, changed: 0
    </td>
  </tr>          <tr style="background-color: #def;">
    <td>
      What: Hoss Man deleted a comment<br/>
      Space: solr:<br/>
      Page: <a href="https://cwiki.apache.org/confluence/display/solr/Getting+Started?focusedCommentId=62691549">Re: Getting Started</a><br/>
      Excerpt: definitely a great post  jadibd.com
    </td>
  </tr>          <tr><td colspan="2" style="border-bottom: 1pt solid red; border-top: 1pt solid red;"><center>^ New Notifications Since You Last Checked ^</center></td></tr>          <tr style="">
    <td>
      What: surya ferdy commented on a page<br/>
      Space: solr:<br/>
      Page: <a href="https://cwiki.apache.org/confluence/display/solr/Getting+Started?focusedCommentId=62691549">Re: Getting Started</a><br/>
      Excerpt: definitely a great post  jadibd.com
    </td>
  </tr>
</table></body></html>"""

        notification_store = {}

        final_notifications_store = NotificationsStore()

        store_writer = Mock()
        store_writer.get_from_binary.side_effect = stub(
            (call('confluence-notifications'), notification_store),
            (call('most-recently-seen'), 1460183824)
        )
        store_writer.store_as_binary.side_effect = stub(
            (call('confluence-notifications', final_notifications_store), True),
            (call('most-recently-seen', 1460183824), True)
        )

        expected_message = ("Subject: Notification Digest: 1 new notification(s)\n"
                            + MAIL_HDR + expected_payload + "\n\n-----NOTIFICATION_BOUNDARY-5678")

        digest_inbox_proxy = Mock()
        digest_inbox_proxy.delete_previous_message.side_effect = stub((call(), True))
        digest_inbox_proxy.append.side_effect = stub((call(expected_message), True))

        digesters = []
        digester = ConfluenceNotificationDigester(store_writer, "confluence@apache.org", "Apache")  ## What we are testing
        digester.notification_boundary_rand = "-5678"  # no random number for the email's notification boundary
        digesters.append(digester)

        digestion_processor = DigestionProcessor(None, None, digesters, False, "ph@example.com", False, "INBOX")

        unmatched_to_move = []
        to_delete_from_notification_folder = []

        digestion_processor.process_incoming_notification(1234, digesters, COMMENT_ADDED, to_delete_from_notification_folder, unmatched_to_move, False)
        digestion_processor.process_incoming_notification(1235, digesters, COMMENT_DELETED, to_delete_from_notification_folder, unmatched_to_move, False)
        digestion_processor.process_incoming_notification(1236, digesters, PAGE_EDITED, to_delete_from_notification_folder, unmatched_to_move, False)

        digester.rewrite_digest_emails(digest_inbox_proxy, has_previous_message=True,
                                       previously_seen=False, sender_to_implicate="ph@example.com")

        self.assertEqual(digest_inbox_proxy.mock_calls, [call.delete_previous_message(), call.append(expected_message)])

        calls = store_writer.mock_calls
        self.assertEqual(calls, [
            call.get_from_binary('confluence-notifications'),
            call.get_from_binary('most-recently-seen'),
            call.store_as_binary('confluence-notifications', {
                1460183824: {'space': 'solr',
                             'line_here': True,
                             'who': 'surya ferdy',
                             'excerpt': 'definitely a great post  jadibd.com',
                             'doc_text': 'Re: Getting Started',
                             'doc_url': 'https://cwiki.apache.org/confluence/display/solr/Getting+Started?focusedCommentId=62691549',
                             'event': 'surya ferdy commented on a page'},
                1460400060: {'space': 'solr',
                             'who': 'Hoss Man',
                             'excerpt': 'definitely a great post  jadibd.com',
                             'doc_text': 'Re: Getting Started',
                             'doc_url': 'https://cwiki.apache.org/confluence/display/solr/Getting+Started?focusedCommentId=62691549',
                             'event': 'Hoss Man deleted a comment'},
                1460535327: {'space': 'solr',
                             'who': 'Noble Paul',
                             'excerpt': 'Page nodes added: 4, removed: 0, changed: 0',
                             'doc_text': 'Config API',
                             'doc_url': 'https://cwiki.apache.org/confluence/display/solr/Config+API',
                             'event': 'Noble Paul edited a page'}
            }),
            call.store_as_binary('most-recently-seen', 1460183824)])
        self.assertEqual(len(unmatched_to_move), 0)
        self.assertEqual(str(to_delete_from_notification_folder), "[1234, 1235, 1236]")
        self.assertEqual(len(final_notifications_store.notifications), 3)


COMMENT_ADDED = """Date: Sat, 9 Apr 2016 06:37:04 +0000
From: "surya ferdy (Confluence)" <confluence@apache.org>
To: <paul_hamm@example.com>
Message-ID: <731544647.1144503.1460183824932.JavaMail.confluence@cwiki-vm4>
Subject: [CONF] Apache Solr Reference Guide > Getting Started
Content-Type: multipart/related;
	boundary="----=_Part_1144502_1498730838.1460183824926"
X-ATLASSIAN-NOTIFICATIONS-VERSION: 6.4.0
Auto-Submitted: auto-generated
Precedence: bulk
Content-Type: text/html; charset="UTF-8"
Return-Path: confluence@apache.org
MIME-Version: 1.0

------=_Part_1144502_1498730838.1460183824926
Content-Type: text/html; charset="UTF-8"
Content-Transfer-Encoding: quoted-printable
Content-Disposition: inline

<html><head>
<meta http-equiv=3D"Content-Type" content=3D"text/html; charset=3Dutf-8">=20
<meta name=3D"viewport" content=3D"width=3Ddevice-width, initial-scale=3D1.=
0, maximum-scale=3D1.0">=20
<base href=3D"https://cwiki.apache.org/confluence">=20
<title>Message Title</title> =20
</head>
<body>
<table id=3D"background-table" cellpadding=3D"0" cellspacing=3D"0" width=3D=
"100%" style=3D"border-collapse: collapse; mso-table-lspace: 0pt; mso-table=
-rspace: 0pt; color: #333; background-color: #f5f5f5">=20
<tbody>=20
<tr>=20
<td id=3D"header-pattern-container" style=3D"padding: 0px; border-collapse:=
 collapse; padding: 10px 20px">=20
<table id=3D"header-pattern" cellspacing=3D"0" cellpadding=3D"0" border=3D"=
0" style=3D"border-collapse: collapse; mso-table-lspace: 0pt; mso-table-rsp=
ace: 0pt; color: #333">=20
<tbody>=20
<tr>=20
<td id=3D"header-avatar-image-container" valign=3D"top" style=3D"padding: 0=
px; border-collapse: collapse; vertical-align: top; width: 32px; padding-ri=
ght: 9px"><a href=3D"https://cwiki.apache.org/confluence/display/~banyuitua=
ir19?src=3Dmail&amp;src.mail.timestamp=3D1460183824702&amp;src.mail.notific=
ation=3Dcom.atlassian.confluence.plugins.confluence-content-notifications-p=
lugin%3Acomment-created-notification&amp;src.mail.recipient=3D8aa980874ebf4=
c1f0153f8e84cef212a" style=3D"color: #3b73af; text-decoration: none"><img i=
d=3D"header-avatar-image" class=3D"image_fix" src=3D"cid:avatar_c9ee7c28225=
bd8d9b71f70f64bf2c5a4" height=3D"32" width=3D"32" border=3D"0" style=3D"bor=
der-radius: 3px; vertical-align: top"></a></td>
<td id=3D"header-text-container" valign=3D"middle" style=3D"padding: 0px; b=
order-collapse: collapse; vertical-align: middle; font-family: Arial, sans-=
serif; font-size: 14px; line-height: 20px; mso-line-height-rule: exactly; m=
so-text-raise: 1px">surya ferdy <strong>commented</strong> on a page</td>=20
</tr>=20
</tbody>=20
</table> </td>=20
</tr>=20
<!-- End Header pattern -->=20
<tr>=20
<td id=3D"email-content-container" style=3D"padding: 0px; border-collapse: =
collapse; padding: 0 20px">=20
<table id=3D"email-content-table" cellspacing=3D"0" cellpadding=3D"0" borde=
r=3D"0" width=3D"100%" style=3D"border-collapse: collapse; mso-table-lspace=
: 0pt; mso-table-rspace: 0pt; color: #333; border-spacing: 0; border-collap=
se: separate">=20
<tbody>=20
<tr>=20
<td class=3D"email-content-rounded-top mobile-expand" style=3D"padding: 0px=
; border-collapse: collapse; color: #fff; padding: 0 15px 0 16px; height: 1=
5px; background-color: #fff; border-left: 1px solid #ccc; border-top: 1px s=
olid #ccc; border-right: 1px solid #ccc; border-bottom: 0; border-top-right=
-radius: 5px; border-top-left-radius: 5px">&nbsp;</td>=20
</tr>=20
<tr>=20
<td class=3D"email-content-main mobile-expand" style=3D"padding: 0px; borde=
r-collapse: collapse; border-left: 1px solid #ccc; border-right: 1px solid =
#ccc; border-top: 0; border-bottom: 0; padding: 0 15px 15px 16px; backgroun=
d-color: #fff">=20
<table id=3D"page-title-pattern" cellspacing=3D"0" cellpadding=3D"0" border=
=3D"0" width=3D"100%" style=3D"border-collapse: collapse; mso-table-lspace:=
 0pt; mso-table-rspace: 0pt; color: #333">=20
<tbody>=20
<tr>=20
<td id=3D"page-title-pattern-icon-image-container" valign=3D"top" style=3D"=
padding: 0px; border-collapse: collapse; width: 16px; vertical-align: top">=
=20
<table cellspacing=3D"0" cellpadding=3D"0" border=3D"0" style=3D"border-col=
lapse: collapse; mso-table-lspace: 0pt; mso-table-rspace: 0pt; color: #333"=
>=20
<tbody>=20
<tr>=20
<td id=3D"page-title-pattern-icon-image-container-cell" style=3D"padding: 0=
px; border-collapse: collapse; width: 16px; padding: 9px 8px 0px 0px; mso-t=
ext-raise: 5px; mso-line-height-rule: exactly"><a href=3D"https://cwiki.apa=
che.org/confluence/display/solr/Getting&#43;Started?focusedCommentId=3D6269=
1549&amp;src=3Dmail&amp;src.mail.timestamp=3D1460183824702&amp;src.mail.not=
ification=3Dcom.atlassian.confluence.plugins.confluence-content-notificatio=
ns-plugin%3Acomment-created-notification&amp;src.mail.recipient=3D8aa980874=
ebf4c1f0153f8e84cef212a&amp;src.mail.action=3Dview#comment-62691549" title=
=3D"comment icon" style=3D"vertical-align: top;; color: #3b73af; text-decor=
ation: none"><img style=3D"vertical-align: top; display: block;" src=3D"cid=
:comment-icon" alt=3D"comment icon" title=3D"comment icon" height=3D"16" wi=
dth=3D"16" border=3D"0"></a></td>=20
</tr>=20
</tbody>=20
</table> </td>
<td style=3D"vertical-align: top;; padding: 0px; border-collapse: collapse;=
 padding-right: 5px; font-size: 20px; line-height: 30px; mso-line-height-ru=
le: exactly" id=3D"page-title-pattern-header-container"><span id=3D"page-ti=
tle-pattern-header" style=3D"font-family: Arial, sans-serif; padding: 0; fo=
nt-size: 20px; line-height: 30px; mso-text-raise: 2px; mso-line-height-rule=
: exactly; vertical-align: middle"><a href=3D"https://cwiki.apache.org/conf=
luence/display/solr/Getting&#43;Started?focusedCommentId=3D62691549&amp;src=
=3Dmail&amp;src.mail.timestamp=3D1460183824702&amp;src.mail.notification=3D=
com.atlassian.confluence.plugins.confluence-content-notifications-plugin%3A=
comment-created-notification&amp;src.mail.recipient=3D8aa980874ebf4c1f0153f=
8e84cef212a&amp;src.mail.action=3Dview#comment-62691549" title=3D"Re: Getti=
ng Started" style=3D"color: #3b73af; text-decoration: none">Re: Getting Sta=
rted</a></span></td>=20
</tr>=20
</tbody>=20
</table> </td>=20
</tr>=20
<tr>=20
<td class=3D"email-content-main mobile-expand" style=3D"padding: 0px; borde=
r-collapse: collapse; border-left: 1px solid #ccc; border-right: 1px solid =
#ccc; border-top: 0; border-bottom: 0; padding: 0 15px 15px 16px; backgroun=
d-color: #fff">=20
<table class=3D"content-excerpt-pattern" cellspacing=3D"0" cellpadding=3D"0=
" border=3D"0" width=3D"100%" style=3D"border-collapse: collapse; mso-table=
-lspace: 0pt; mso-table-rspace: 0pt; color: #333; font-family: Arial, sans-=
serif; font-size: 14px; line-height: 20px; mso-line-height-rule: exactly; m=
so-text-raise: 1px">=20
<tbody>=20
<tr>=20
<td class=3D"content-excerpt-pattern-container mobile-resize-text " style=
=3D"padding: 0px; border-collapse: collapse; padding: 0 0 0 24px"> <p style=
=3D"margin: 10px 0 0 0; margin-top: 0">definitely a great post</p> <p style=
=3D"margin: 10px 0 0 0"> <a href=3D"http://www.jadibd.com" class=3D"externa=
l-link" rel=3D"nofollow" style=3D"color: #3b73af; text-decoration: none">ja=
dibd.com</a><a rel=3D"nofollow" style=3D"color: #3b73af; text-decoration: n=
one"></a> </p> </td>=20
</tr>=20
</tbody>=20
</table> </td>=20
</tr>=20
<tr>=20
<td class=3D"email-content-main mobile-expand action-padding last-row-paddi=
ng" style=3D"padding: 0px; border-collapse: collapse; border-left: 1px soli=
d #ccc; border-right: 1px solid #ccc; border-top: 0; border-bottom: 0; padd=
ing: 0 15px 15px 16px; background-color: #fff; padding-bottom: 10px; paddin=
g-bottom: 10px">=20
<table id=3D"actions-pattern" cellspacing=3D"0" cellpadding=3D"0" border=3D=
"0" width=3D"100%" style=3D"border-collapse: collapse; mso-table-lspace: 0p=
t; mso-table-rspace: 0pt; color: #333; font-family: Arial, sans-serif; font=
-size: 14px; line-height: 20px; mso-line-height-rule: exactly; mso-text-rai=
se: 1px">=20
<tbody>=20
<tr>=20
<td id=3D"actions-pattern-container" valign=3D"middle" style=3D"padding: 0p=
x; border-collapse: collapse; padding: 15px 0 0 24px; vertical-align: middl=
e">=20
<table align=3D"left" style=3D"border-collapse: collapse; mso-table-lspace:=
 0pt; mso-table-rspace: 0pt; color: #333">=20
<tbody>=20
<tr>=20
<td class=3D"actions-pattern-action-icon-container" style=3D"padding: 0px; =
border-collapse: collapse; font-family: Arial, sans-serif; font-size: 14px;=
 line-height: 20px; mso-line-height-rule: exactly; mso-text-raise: 0px; ver=
tical-align: middle"><a href=3D"https://cwiki.apache.org/confluence/display=
/solr/Getting&#43;Started?replyToComment=3D62691549&amp;src=3Dmail&amp;src.=
mail.timestamp=3D1460183824702&amp;src.mail.notification=3Dcom.atlassian.co=
nfluence.plugins.confluence-content-notifications-plugin%3Acomment-created-=
notification&amp;src.mail.recipient=3D8aa980874ebf4c1f0153f8e84cef212a&amp;=
src.mail.action=3Dreply#comment-62691549" title=3D"Reply Icon" style=3D"col=
or: #3b73af; text-decoration: none"><img class=3D"actions-pattern-action-ic=
on-image" height=3D"16" width=3D"16" border=3D"0" title=3D"Reply Icon" src=
=3D"cid:com.atlassian.confluence.plugins.confluence-email-resources%3Areply=
-to-comment-email-adg-footer-item%3Aicon" alt=3D"Reply Icon" style=3D"verti=
cal-align: middle"></a></td>
<td class=3D"actions-pattern-action-text-container" style=3D"padding: 0px; =
border-collapse: collapse; font-family: Arial, sans-serif; font-size: 14px;=
 line-height: 20px; mso-line-height-rule: exactly; mso-text-raise: 4px; pad=
ding-left: 5px; white-space: nowrap"><a href=3D"https://cwiki.apache.org/co=
nfluence/display/solr/Getting&#43;Started?replyToComment=3D62691549&amp;src=
=3Dmail&amp;src.mail.timestamp=3D1460183824702&amp;src.mail.notification=3D=
com.atlassian.confluence.plugins.confluence-content-notifications-plugin%3A=
comment-created-notification&amp;src.mail.recipient=3D8aa980874ebf4c1f0153f=
8e84cef212a&amp;src.mail.action=3Dreply#comment-62691549" title=3D"Reply" s=
tyle=3D"color: #3b73af; text-decoration: none">Reply</a></td>
<td class=3D"actions-pattern-action-bull" style=3D"padding: 0px; border-col=
lapse: collapse; font-family: Arial, sans-serif; font-size: 14px; line-heig=
ht: 20px; mso-line-height-rule: exactly; mso-text-raise: 4px; color: #999; =
padding: 0 5px">=E2=80=A2</td>=20
</tr>=20
</tbody>=20
</table>=20
<table style=3D"border-collapse: collapse; mso-table-lspace: 0pt; mso-table=
-rspace: 0pt; color: #333">=20
<tbody>=20
<tr>=20
<td class=3D"actions-pattern-action-icon-container" style=3D"padding: 0px; =
border-collapse: collapse; font-family: Arial, sans-serif; font-size: 14px;=
 line-height: 20px; mso-line-height-rule: exactly; mso-text-raise: 0px; ver=
tical-align: middle"><a href=3D"https://cwiki.apache.org/confluence/plugins=
/likes/like.action?contentId=3D62691549&amp;src=3Dmail&amp;src.mail.timesta=
mp=3D1460183824702&amp;src.mail.notification=3Dcom.atlassian.confluence.plu=
gins.confluence-content-notifications-plugin%3Acomment-created-notification=
&amp;src.mail.recipient=3D8aa980874ebf4c1f0153f8e84cef212a&amp;src.mail.act=
ion=3Dlike" title=3D"Like Icon" style=3D"color: #3b73af; text-decoration: n=
one"><img class=3D"actions-pattern-action-icon-image" height=3D"16" width=
=3D"16" border=3D"0" title=3D"Like Icon" src=3D"cid:com.atlassian.confluenc=
e.plugins.confluence-like%3Aview-email-adg-content-item%3Aicon" alt=3D"Like=
 Icon" style=3D"vertical-align: middle"></a></td>
<td class=3D"actions-pattern-action-text-container" style=3D"padding: 0px; =
border-collapse: collapse; font-family: Arial, sans-serif; font-size: 14px;=
 line-height: 20px; mso-line-height-rule: exactly; mso-text-raise: 4px; pad=
ding-left: 5px; white-space: nowrap"><a href=3D"https://cwiki.apache.org/co=
nfluence/plugins/likes/like.action?contentId=3D62691549&amp;src=3Dmail&amp;=
src.mail.timestamp=3D1460183824702&amp;src.mail.notification=3Dcom.atlassia=
n.confluence.plugins.confluence-content-notifications-plugin%3Acomment-crea=
ted-notification&amp;src.mail.recipient=3D8aa980874ebf4c1f0153f8e84cef212a&=
amp;src.mail.action=3Dlike" title=3D"Like" style=3D"color: #3b73af; text-de=
coration: none">Like</a></td>=20
</tr>=20
</tbody>=20
</table> </td>=20
</tr>=20
</tbody>=20
</table> </td>=20
</tr>=20
<tr>=20
<td class=3D"email-content-rounded-bottom mobile-expand" style=3D"padding: =
0px; border-collapse: collapse; color: #fff; height: 5px; line-height: 5px;=
 padding: 0 15px 0 16px; background-color: #fff; border-bottom-right-radius=
: 5px; border-bottom-left-radius: 5px; border-top: 0; border-left: 1px soli=
d #ccc; border-bottom: 1px solid #ccc; border-right: 1px solid #ccc; mso-li=
ne-height-rule: exactly">&nbsp;</td>=20
</tr>=20
</tbody>=20
</table> </td>=20
</tr>=20
<tr>=20
<td id=3D"footer-pattern" style=3D"padding: 0px; border-collapse: collapse;=
 padding: 12px 20px">=20
<table id=3D"footer-pattern-container" cellspacing=3D"0" cellpadding=3D"0" =
border=3D"0" width=3D"100%" style=3D"border-collapse: collapse; mso-table-l=
space: 0pt; mso-table-rspace: 0pt; color: #333">=20
<tbody>=20
<tr>=20
<td id=3D"footer-pattern-links-container" width=3D"100%" style=3D"padding: =
0px; border-collapse: collapse; color: #999; font-size: 12px; line-height: =
18px; font-family: Arial, sans-serif; mso-line-height-rule: exactly; mso-te=
xt-raise: 2px">=20
<table align=3D"left" style=3D"border-collapse: collapse; mso-table-lspace:=
 0pt; mso-table-rspace: 0pt; color: #333; font-size: 12px; line-height: 18p=
x; font-family: Arial, sans-serif; mso-line-height-rule: exactly; mso-text-=
raise: 2px">=20
<tbody>=20
<tr>=20
<td class=3D"footer-pattern-links mobile-resize-text" style=3D"padding: 0px=
; border-collapse: collapse"><a href=3D"https://cwiki.apache.org/confluence=
/users/removespacenotification.action?spaceKey=3Dsolr&amp;src=3Dmail&amp;sr=
c.mail.timestamp=3D1460183824702&amp;src.mail.notification=3Dcom.atlassian.=
confluence.plugins.confluence-content-notifications-plugin%3Acomment-create=
d-notification&amp;src.mail.recipient=3D8aa980874ebf4c1f0153f8e84cef212a&am=
p;src.mail.action=3Dstop-watching" title=3D"" style=3D"color: #3b73af; text=
-decoration: none">Stop watching space</a></td>
<td class=3D"footer-pattern-links-bull" style=3D"padding: 0px; border-colla=
pse: collapse; padding: 0 5px; color: #999">=E2=80=A2</td>=20
</tr>=20
</tbody>=20
</table>=20
<table style=3D"border-collapse: collapse; mso-table-lspace: 0pt; mso-table=
-rspace: 0pt; color: #333; font-size: 12px; line-height: 18px; font-family:=
 Arial, sans-serif; mso-line-height-rule: exactly; mso-text-raise: 2px">=20
<tbody>=20
<tr>=20
<td class=3D"footer-pattern-links mobile-resize-text" style=3D"padding: 0px=
; border-collapse: collapse"><a href=3D"https://cwiki.apache.org/confluence=
/users/editmyemailsettings.action?src=3Dmail&amp;src.mail.timestamp=3D14601=
83824702&amp;src.mail.notification=3Dcom.atlassian.confluence.plugins.confl=
uence-content-notifications-plugin%3Acomment-created-notification&amp;src.m=
ail.recipient=3D8aa980874ebf4c1f0153f8e84cef212a&amp;src.mail.action=3Dmana=
ge" title=3D"" style=3D"color: #3b73af; text-decoration: none">Manage notif=
ications</a></td>=20
</tr>=20
</tbody>=20
</table> </td>
<td id=3D"footer-pattern-logo-desktop-container" rowspan=3D"2" valign=3D"to=
p" style=3D"padding: 0px; border-collapse: collapse; padding-left: 20px; ve=
rtical-align: top">=20
<table style=3D"border-collapse: collapse; mso-table-lspace: 0pt; mso-table=
-rspace: 0pt; color: #333">=20
<tbody>=20
<tr>=20
<td id=3D"footer-pattern-logo-desktop-padding" style=3D"padding: 0px; borde=
r-collapse: collapse; padding-top: 3px"><img id=3D"footer-pattern-logo-desk=
top" src=3D"cid:footer-desktop-logo" alt=3D"Confluence logo big" title=3D"C=
onfluence logo big" width=3D"132" height=3D"20" class=3D"image_fix"></td>=20
</tr>=20
</tbody>=20
</table> </td>=20
</tr>=20
<tr>=20
<td id=3D"footer-pattern-text" class=3D"mobile-resize-text" width=3D"100%" =
style=3D"padding: 0px; border-collapse: collapse; color: #999; font-size: 1=
2px; line-height: 18px; font-family: Arial, sans-serif; mso-line-height-rul=
e: exactly; mso-text-raise: 2px; display: none">This message was sent by At=
lassian Confluence 5.8.4<br> <img id=3D"footer-pattern-logo-mobile" src=3D"=
cid:footer-mobile-logo" alt=3D"" title=3D"" width=3D"0" height=3D"0" style=
=3D"display: none; mso-hide: all"></td>=20
</tr>=20
</tbody>=20
</table> </td>=20
</tr>=20
</tbody>=20
</table>=20
<table id=3D"sealed-section" border=3D"0" cellpadding=3D"0" cellspacing=3D"=
0" width=3D"0" style=3D"border-collapse: collapse; mso-table-lspace: 0pt; m=
so-table-rspace: 0pt; color: #333; display: none">=20
<tbody>=20
<tr>=20
<td style=3D"padding: 0px; border-collapse: collapse; border: 0; font-size:=
 0px; line-height: 0; mso-line-height-rule: exactly"></td>=20
</tr>=20
</tbody>=20
</table>
</body>
</html>=

------=_Part_1144502_1498730838.1460183824926
"""

COMMENT_DELETED = """Date: Mon, 11 Apr 2016 18:41:00 +0000
From: "Hoss Man (Confluence)" <confluence@apache.org>
To: <paul_hamm@example.com>
Message-ID: <contentId-62691549-1586493860@confluence.localhost>
Subject: [CONF] Apache Solr Reference Guide > Getting Started
Content-Type: multipart/related;
	boundary="----=_Part_1152161_850119877.1460400060674"
Auto-Submitted: auto-generated
Precedence: bulk
Return-Path: confluence@apache.org
MIME-Version: 1.0

------=_Part_1152161_850119877.1460400060674
Content-Type: text/html; charset="UTF-8"
Content-Transfer-Encoding: quoted-printable
Content-Disposition: inline

<html><head>
<meta http-equiv=3D"Content-Type" content=3D"text/html; charset=3Dutf-8">=20
<meta name=3D"viewport" content=3D"width=3Ddevice-width, initial-scale=3D1.=
0, maximum-scale=3D1.0">=20
<base href=3D"https://cwiki.apache.org/confluence">=20
<title>Message Title</title> =20
</head>
<body>
<table id=3D"background-table" cellpadding=3D"0" cellspacing=3D"0" width=3D=
"100%" style=3D"border-collapse: collapse; mso-table-lspace: 0pt; mso-table=
-rspace: 0pt; color: #333; background-color: #f5f5f5">=20
<tbody>=20
<tr>=20
<td id=3D"header-pattern-container" style=3D"padding: 0px; border-collapse:=
 collapse; padding: 10px 20px">=20
<table id=3D"header-pattern" cellspacing=3D"0" cellpadding=3D"0" border=3D"=
0" style=3D"border-collapse: collapse; mso-table-lspace: 0pt; mso-table-rsp=
ace: 0pt; color: #333">=20
<tbody>=20
<tr>=20
<td id=3D"header-avatar-image-container" valign=3D"top" style=3D"padding: 0=
px; border-collapse: collapse; vertical-align: top; width: 32px; padding-ri=
ght: 9px"><a href=3D"https://cwiki.apache.org/confluence/display/~hossman?s=
rc=3Demail" style=3D"color: #3b73af; text-decoration: none"><img id=3D"head=
er-avatar-image" class=3D"image_fix" src=3D"cid:avatar_571812907fb6dbb71722=
da66de4232ab" height=3D"32" width=3D"32" border=3D"0" style=3D"border-radiu=
s: 3px; vertical-align: top"></a></td>
<td id=3D"header-text-container" valign=3D"middle" style=3D"padding: 0px; b=
order-collapse: collapse; vertical-align: middle; font-family: Arial, sans-=
serif; font-size: 14px; line-height: 20px; mso-line-height-rule: exactly; m=
so-text-raise: 1px">Hoss Man <strong>deleted</strong> a comment</td>=20
</tr>=20
</tbody>=20
</table> </td>=20
</tr>=20
<!-- End Header pattern -->=20
<tr>=20
<td id=3D"email-content-container" style=3D"padding: 0px; border-collapse: =
collapse; padding: 0 20px">=20
<table id=3D"email-content-table" cellspacing=3D"0" cellpadding=3D"0" borde=
r=3D"0" width=3D"100%" style=3D"border-collapse: collapse; mso-table-lspace=
: 0pt; mso-table-rspace: 0pt; color: #333; border-spacing: 0; border-collap=
se: separate">=20
<tbody>=20
<tr>=20
<td class=3D"email-content-rounded-top mobile-expand" style=3D"padding: 0px=
; border-collapse: collapse; color: #fff; padding: 0 15px 0 16px; height: 1=
5px; background-color: #fff; border-left: 1px solid #ccc; border-top: 1px s=
olid #ccc; border-right: 1px solid #ccc; border-bottom: 0; border-top-right=
-radius: 5px; border-top-left-radius: 5px">&nbsp;</td>=20
</tr>=20
<tr>=20
<td class=3D"email-content-main mobile-expand" style=3D"padding: 0px; borde=
r-collapse: collapse; border-left: 1px solid #ccc; border-right: 1px solid =
#ccc; border-top: 0; border-bottom: 0; padding: 0 15px 15px 16px; backgroun=
d-color: #fff">=20
<table id=3D"page-title-pattern" cellspacing=3D"0" cellpadding=3D"0" border=
=3D"0" width=3D"100%" style=3D"border-collapse: collapse; mso-table-lspace:=
 0pt; mso-table-rspace: 0pt; color: #333">=20
<tbody>=20
<tr>=20
<td id=3D"page-title-pattern-icon-image-container" valign=3D"top" style=3D"=
padding: 0px; border-collapse: collapse; width: 16px; vertical-align: top">=
=20
<table cellspacing=3D"0" cellpadding=3D"0" border=3D"0" style=3D"border-col=
lapse: collapse; mso-table-lspace: 0pt; mso-table-rspace: 0pt; color: #333"=
>=20
<tbody>=20
<tr>=20
<td id=3D"page-title-pattern-icon-image-container-cell" style=3D"padding: 0=
px; border-collapse: collapse; width: 16px; padding: 9px 8px 0px 0px; mso-t=
ext-raise: 5px; mso-line-height-rule: exactly"><a href=3D"https://cwiki.apa=
che.org/confluence/display/solr/Getting&#43;Started?focusedCommentId=3D6269=
1549#comment-62691549" title=3D"comment icon" style=3D"vertical-align: top;=
; color: #3b73af; text-decoration: none"><img style=3D"vertical-align: top;=
 display: block;" src=3D"cid:comment-icon" alt=3D"comment icon" title=3D"co=
mment icon" height=3D"16" width=3D"16" border=3D"0"></a></td>=20
</tr>=20
</tbody>=20
</table> </td>
<td style=3D"vertical-align: top;; padding: 0px; border-collapse: collapse;=
 padding-right: 5px; font-size: 20px; line-height: 30px; mso-line-height-ru=
le: exactly" id=3D"page-title-pattern-header-container"><span id=3D"page-ti=
tle-pattern-header" class=3D"content-deleted-color" style=3D"font-family: A=
rial, sans-serif; padding: 0; font-size: 20px; line-height: 30px; mso-text-=
raise: 2px; mso-line-height-rule: exactly; vertical-align: middle; color: #=
707070"><a href=3D"https://cwiki.apache.org/confluence/display/solr/Getting=
&#43;Started?focusedCommentId=3D62691549#comment-62691549" title=3D"Re: Get=
ting Started" style=3D"color: #3b73af; text-decoration: none; color: #70707=
0">Re: Getting Started</a></span>&nbsp;<span class=3D"content-deleted-lozen=
ge" style=3D"font-family: Arial, sans-serif; background-color: #d04437; col=
or: #fff; border-radius: 3px; font-size: 11px; font-weight: bold; mso-line-=
height-rule: exactly; line-height: 11px; text-align: center; vertical-align=
: middle; border: 2px solid #d04437; border-right-width: 4px; border-left-w=
idth: 4px; mso-text-raise: 2px; mso-border-alt: solid #d04437 2px; mso-bord=
er-alt: solid #d04437 4px">DELETED</span></td>=20
</tr>=20
</tbody>=20
</table> </td>=20
</tr>=20
<tr>=20
<td class=3D"email-content-main mobile-expand last-row-padding" style=3D"pa=
dding: 0px; border-collapse: collapse; border-left: 1px solid #ccc; border-=
right: 1px solid #ccc; border-top: 0; border-bottom: 0; padding: 0 15px 15p=
x 16px; background-color: #fff; padding-bottom: 10px">=20
<table class=3D"content-excerpt-pattern" cellspacing=3D"0" cellpadding=3D"0=
" border=3D"0" width=3D"100%" style=3D"border-collapse: collapse; mso-table=
-lspace: 0pt; mso-table-rspace: 0pt; color: #333; font-family: Arial, sans-=
serif; font-size: 14px; line-height: 20px; mso-line-height-rule: exactly; m=
so-text-raise: 1px">=20
<tbody>=20
<tr>=20
<td class=3D"content-excerpt-pattern-container mobile-resize-text content-d=
eleted-color" style=3D"padding: 0px; border-collapse: collapse; padding: 0 =
0 0 24px; color: #707070"> <p style=3D"margin: 10px 0 0 0; margin-top: 0">d=
efinitely a great post</p> <p style=3D"margin: 10px 0 0 0"> <a href=3D"http=
://www.jadibd.com" class=3D"external-link" rel=3D"nofollow" style=3D"color:=
 #3b73af; text-decoration: none; color: #707070">jadibd.com</a><a rel=3D"no=
follow" style=3D"color: #3b73af; text-decoration: none; color: #707070"></a=
> </p> </td>=20
</tr>=20
</tbody>=20
</table> </td>=20
</tr>=20
<tr>=20
<td class=3D"email-content-rounded-bottom mobile-expand" style=3D"padding: =
0px; border-collapse: collapse; color: #fff; height: 5px; line-height: 5px;=
 padding: 0 15px 0 16px; background-color: #fff; border-bottom-right-radius=
: 5px; border-bottom-left-radius: 5px; border-top: 0; border-left: 1px soli=
d #ccc; border-bottom: 1px solid #ccc; border-right: 1px solid #ccc; mso-li=
ne-height-rule: exactly">&nbsp;</td>=20
</tr>=20
</tbody>=20
</table> </td>=20
</tr>=20
<tr>=20
<td id=3D"footer-pattern" style=3D"padding: 0px; border-collapse: collapse;=
 padding: 12px 20px">=20
<table id=3D"footer-pattern-container" cellspacing=3D"0" cellpadding=3D"0" =
border=3D"0" width=3D"100%" style=3D"border-collapse: collapse; mso-table-l=
space: 0pt; mso-table-rspace: 0pt; color: #333">=20
<tbody>=20
<tr>=20
<td id=3D"footer-pattern-links-container" width=3D"100%" style=3D"padding: =
0px; border-collapse: collapse; color: #999; font-size: 12px; line-height: =
18px; font-family: Arial, sans-serif; mso-line-height-rule: exactly; mso-te=
xt-raise: 2px">=20
<table align=3D"left" style=3D"border-collapse: collapse; mso-table-lspace:=
 0pt; mso-table-rspace: 0pt; color: #333; font-size: 12px; line-height: 18p=
x; font-family: Arial, sans-serif; mso-line-height-rule: exactly; mso-text-=
raise: 2px">=20
<tbody>=20
<tr>=20
<td class=3D"footer-pattern-links mobile-resize-text" style=3D"padding: 0px=
; border-collapse: collapse"><a href=3D"https://cwiki.apache.org/confluence=
/users/removespacenotification.action?spaceKey=3Dsolr" title=3D"" style=3D"=
color: #3b73af; text-decoration: none">Stop watching space</a></td>
<td class=3D"footer-pattern-links-bull" style=3D"padding: 0px; border-colla=
pse: collapse; padding: 0 5px; color: #999">=E2=80=A2</td>=20
</tr>=20
</tbody>=20
</table>=20
<table style=3D"border-collapse: collapse; mso-table-lspace: 0pt; mso-table=
-rspace: 0pt; color: #333; font-size: 12px; line-height: 18px; font-family:=
 Arial, sans-serif; mso-line-height-rule: exactly; mso-text-raise: 2px">=20
<tbody>=20
<tr>=20
<td class=3D"footer-pattern-links mobile-resize-text" style=3D"padding: 0px=
; border-collapse: collapse"><a href=3D"https://cwiki.apache.org/confluence=
/users/editmyemailsettings.action" title=3D"" style=3D"color: #3b73af; text=
-decoration: none">Manage notifications</a></td>=20
</tr>=20
</tbody>=20
</table> </td>
<td id=3D"footer-pattern-logo-desktop-container" rowspan=3D"2" valign=3D"to=
p" style=3D"padding: 0px; border-collapse: collapse; padding-left: 20px; ve=
rtical-align: top">=20
<table style=3D"border-collapse: collapse; mso-table-lspace: 0pt; mso-table=
-rspace: 0pt; color: #333">=20
<tbody>=20
<tr>=20
<td id=3D"footer-pattern-logo-desktop-padding" style=3D"padding: 0px; borde=
r-collapse: collapse; padding-top: 3px"><img id=3D"footer-pattern-logo-desk=
top" src=3D"cid:footer-desktop-logo" alt=3D"Confluence logo big" title=3D"C=
onfluence logo big" width=3D"132" height=3D"20" class=3D"image_fix"></td>=20
</tr>=20
</tbody>=20
</table> </td>=20
</tr>=20
<tr>=20
<td id=3D"footer-pattern-text" class=3D"mobile-resize-text" width=3D"100%" =
style=3D"padding: 0px; border-collapse: collapse; color: #999; font-size: 1=
2px; line-height: 18px; font-family: Arial, sans-serif; mso-line-height-rul=
e: exactly; mso-text-raise: 2px; display: none"> This message was sent by A=
tlassian Confluence 5.8.4 <br> <img id=3D"footer-pattern-logo-mobile" src=
=3D"cid:footer-mobile-logo" alt=3D"" title=3D"" width=3D"0" height=3D"0" st=
yle=3D"display: none; mso-hide: all"></td>=20
</tr>=20
</tbody>=20
</table> </td>=20
</tr>=20
</tbody>=20
</table>=20
<table id=3D"sealed-section" border=3D"0" cellpadding=3D"0" cellspacing=3D"=
0" width=3D"0" style=3D"border-collapse: collapse; mso-table-lspace: 0pt; m=
so-table-rspace: 0pt; color: #333; display: none">=20
<tbody>=20
<tr>=20
<td style=3D"padding: 0px; border-collapse: collapse; border: 0; font-size:=
 0px; line-height: 0; mso-line-height-rule: exactly"></td>=20
</tr>=20
</tbody>=20
</table>
</body>
</html>=




------=_Part_1152161_850119877.1460400060674--
"""

PAGE_EDITED = """Date: Wed, 13 Apr 2016 08:15:27 +0000
From: "Noble Paul (Confluence)" <confluence@apache.org>
To: <paul_hamm@example.com>
Message-ID: <1334689970.1157938.1460535327926.JavaMail.confluence@cwiki-vm4>
Subject: [CONF] Apache Solr Reference Guide > Config API
Content-Type: multipart/related;
	boundary="----=_Part_1157937_100703508.1460535327916"
X-ATLASSIAN-NOTIFICATIONS-VERSION: 6.4.0
Auto-Submitted: auto-generated
Precedence: bulk
Return-Path: confluence@apache.org
MIME-Version: 1.0

------=_Part_1157937_100703508.1460535327916
Content-Type: text/html; charset="UTF-8"
Content-Transfer-Encoding: quoted-printable
Content-Disposition: inline

<html><head>
<meta http-equiv=3D"Content-Type" content=3D"text/html; charset=3Dutf-8">=20
<meta name=3D"viewport" content=3D"width=3Ddevice-width, initial-scale=3D1.=
0, maximum-scale=3D1.0">=20
<base href=3D"https://cwiki.apache.org/confluence">=20
<title>Message Title</title> =20
</head>
<body>
<table id=3D"background-table" cellpadding=3D"0" cellspacing=3D"0" width=3D=
"100%" style=3D"border-collapse: collapse; mso-table-lspace: 0pt; mso-table=
-rspace: 0pt; color: #333; background-color: #f5f5f5">=20
<tbody>=20
<tr>=20
<td id=3D"header-pattern-container" style=3D"padding: 0px; border-collapse:=
 collapse; padding: 10px 20px">=20
<table id=3D"header-pattern" cellspacing=3D"0" cellpadding=3D"0" border=3D"=
0" style=3D"border-collapse: collapse; mso-table-lspace: 0pt; mso-table-rsp=
ace: 0pt; color: #333">=20
<tbody>=20
<tr>=20
<td id=3D"header-avatar-image-container" valign=3D"top" style=3D"padding: 0=
px; border-collapse: collapse; vertical-align: top; width: 32px; padding-ri=
ght: 9px"><a href=3D"https://cwiki.apache.org/confluence/display/~noble.pau=
l@gmail.com?src=3Dmail&amp;src.mail.timestamp=3D1460535327722&amp;src.mail.=
notification=3Dcom.atlassian.confluence.plugins.confluence-content-notifica=
tions-plugin%3Apage-edited-notification&amp;src.mail.recipient=3D8aa980874e=
bf4c1f0153f8e84cef212a" style=3D"color: #3b73af; text-decoration: none"><im=
g id=3D"header-avatar-image" class=3D"image_fix" src=3D"cid:avatar_f28ca7b9=
cf4d9bc13b72a24b1bd9230f" height=3D"32" width=3D"32" border=3D"0" style=3D"=
border-radius: 3px; vertical-align: top"></a></td>
<td id=3D"header-text-container" valign=3D"middle" style=3D"padding: 0px; b=
order-collapse: collapse; vertical-align: middle; font-family: Arial, sans-=
serif; font-size: 14px; line-height: 20px; mso-line-height-rule: exactly; m=
so-text-raise: 1px">Noble Paul <strong>edited</strong> a page</td>=20
</tr>=20
</tbody>=20
</table> </td>=20
</tr>=20
<!-- End Header pattern -->=20
<tr>=20
<td id=3D"email-content-container" style=3D"padding: 0px; border-collapse: =
collapse; padding: 0 20px">=20
<table id=3D"email-content-table" cellspacing=3D"0" cellpadding=3D"0" borde=
r=3D"0" width=3D"100%" style=3D"border-collapse: collapse; mso-table-lspace=
: 0pt; mso-table-rspace: 0pt; color: #333; border-spacing: 0; border-collap=
se: separate">=20
<tbody>=20
<tr>=20
<td class=3D"email-content-rounded-top mobile-expand" style=3D"padding: 0px=
; border-collapse: collapse; color: #fff; padding: 0 15px 0 16px; height: 1=
5px; background-color: #fff; border-left: 1px solid #ccc; border-top: 1px s=
olid #ccc; border-right: 1px solid #ccc; border-bottom: 0; border-top-right=
-radius: 5px; border-top-left-radius: 5px">&nbsp;</td>=20
</tr>=20
<tr>=20
<td class=3D"email-content-main mobile-expand" style=3D"padding: 0px; borde=
r-collapse: collapse; border-left: 1px solid #ccc; border-right: 1px solid =
#ccc; border-top: 0; border-bottom: 0; padding: 0 15px 15px 16px; backgroun=
d-color: #fff">=20
<table id=3D"page-title-pattern" cellspacing=3D"0" cellpadding=3D"0" border=
=3D"0" width=3D"100%" style=3D"border-collapse: collapse; mso-table-lspace:=
 0pt; mso-table-rspace: 0pt; color: #333">=20
<tbody>=20
<tr>=20
<td id=3D"page-title-pattern-icon-image-container" valign=3D"top" style=3D"=
padding: 0px; border-collapse: collapse; width: 16px; vertical-align: top">=
=20
<table cellspacing=3D"0" cellpadding=3D"0" border=3D"0" style=3D"border-col=
lapse: collapse; mso-table-lspace: 0pt; mso-table-rspace: 0pt; color: #333"=
>=20
<tbody>=20
<tr>=20
<td id=3D"page-title-pattern-icon-image-container-cell" style=3D"padding: 0=
px; border-collapse: collapse; width: 16px; padding: 9px 8px 0px 0px; mso-t=
ext-raise: 5px; mso-line-height-rule: exactly"><a href=3D"https://cwiki.apa=
che.org/confluence/display/solr/Config&#43;API?src=3Dmail&amp;src.mail.time=
stamp=3D1460535327722&amp;src.mail.notification=3Dcom.atlassian.confluence.=
plugins.confluence-content-notifications-plugin%3Apage-edited-notification&=
amp;src.mail.recipient=3D8aa980874ebf4c1f0153f8e84cef212a&amp;src.mail.acti=
on=3Dview" title=3D"page icon" style=3D"vertical-align: top;; color: #3b73a=
f; text-decoration: none"><img style=3D"vertical-align: top; display: block=
;" src=3D"cid:page-icon" alt=3D"page icon" title=3D"page icon" height=3D"16=
" width=3D"16" border=3D"0"></a></td>=20
</tr>=20
</tbody>=20
</table> </td>
<td style=3D"vertical-align: top;; padding: 0px; border-collapse: collapse;=
 padding-right: 5px; font-size: 20px; line-height: 30px; mso-line-height-ru=
le: exactly" id=3D"page-title-pattern-header-container"><span id=3D"page-ti=
tle-pattern-header" style=3D"font-family: Arial, sans-serif; padding: 0; fo=
nt-size: 20px; line-height: 30px; mso-text-raise: 2px; mso-line-height-rule=
: exactly; vertical-align: middle"><a href=3D"https://cwiki.apache.org/conf=
luence/display/solr/Config&#43;API?src=3Dmail&amp;src.mail.timestamp=3D1460=
535327722&amp;src.mail.notification=3Dcom.atlassian.confluence.plugins.conf=
luence-content-notifications-plugin%3Apage-edited-notification&amp;src.mail=
.recipient=3D8aa980874ebf4c1f0153f8e84cef212a&amp;src.mail.action=3Dview" t=
itle=3D"Config API" style=3D"color: #3b73af; text-decoration: none">Config =
API</a></span></td>=20
</tr>=20
</tbody>=20
</table> </td>=20
</tr>=20
<tr>=20
<td class=3D"email-content-main mobile-expand" style=3D"padding: 0px; borde=
r-collapse: collapse; border-left: 1px solid #ccc; border-right: 1px solid =
#ccc; border-top: 0; border-bottom: 0; padding: 0 15px 15px 16px; backgroun=
d-color: #fff">=20
<table class=3D"content-excerpt-pattern" cellspacing=3D"0" cellpadding=3D"0=
" border=3D"0" width=3D"100%" style=3D"border-collapse: collapse; mso-table=
-lspace: 0pt; mso-table-rspace: 0pt; color: #333; font-family: Arial, sans-=
serif; font-size: 14px; line-height: 20px; mso-line-height-rule: exactly; m=
so-text-raise: 1px">=20
<tbody>=20
<tr>=20
<td class=3D"content-excerpt-pattern-container mobile-resize-text " style=
=3D"padding: 0px; border-collapse: collapse; padding: 0 0 0 24px"> <p class=
=3D"diff-context-placeholder" style=3D"margin: 10px 0 0 0; margin-top: 0">.=
..</p>=20
<ul class=3D"diff-block-target" style=3D"margin: 10px 0 0 0">=20
<li> <code style=3D"font-family: monospace">/config</code>:&nbsp;retrieve&n=
bsp;or modify the config. GET to retrieve and POST for executing commands</=
li>=20
<li> <code style=3D"font-family: monospace">/config/overlay</code>:&nbsp;re=
trieve the details in the <code style=3D"font-family: monospace">configover=
lay.json</code>&nbsp;alone</li>=20
<li> <code style=3D"font-family: monospace"><span class=3D"diff-html-added"=
 id=3D"added-diff-0" style=3D"font-size: 100%; background-color: #ddfade;">=
/config/params</span></code><span class=3D"diff-html-added" style=3D"font-s=
ize: 100%; background-color: #ddfade;"> : See </span><a href=3D"https://cwi=
ki.apache.org/confluence/display/solr/Request&#43;Parameters&#43;API" rel=
=3D"nofollow" style=3D"color: #3b73af; text-decoration: none"><span class=
=3D"diff-html-added" style=3D"font-size: 100%; background-color: #ddfade;">=
this page</span></a><span class=3D"diff-html-added" style=3D"font-size: 100=
%; background-color: #ddfade;"> for more details</span> </li>=20
</ul> <h2 id=3D"ConfigAPI-Commands" class=3D"diff-block-context" style=3D"m=
argin: 10px 0 0 0; font-size: 20px; font-weight: normal; line-height: 30px;=
 margin: 40px 0 0 0">Commands</h2> <p class=3D"diff-block-context" style=3D=
"margin: 10px 0 0 0">This API uses specific commands to tell Solr what prop=
erty or type of property to add to&nbsp;<code style=3D"font-family: monospa=
ce">configoverlay.json</code>. The commands are passed as part of the data =
sent with the request.</p> <p class=3D"diff-context-placeholder" style=3D"m=
argin: 10px 0 0 0; margin-top: 0">...</p> </td>=20
</tr>=20
</tbody>=20
</table> </td>=20
</tr>=20
<tr>=20
<td class=3D"email-content-main mobile-expand action-padding last-row-paddi=
ng" style=3D"padding: 0px; border-collapse: collapse; border-left: 1px soli=
d #ccc; border-right: 1px solid #ccc; border-top: 0; border-bottom: 0; padd=
ing: 0 15px 15px 16px; background-color: #fff; padding-bottom: 10px; paddin=
g-bottom: 10px">=20
<table id=3D"actions-pattern" cellspacing=3D"0" cellpadding=3D"0" border=3D=
"0" width=3D"100%" style=3D"border-collapse: collapse; mso-table-lspace: 0p=
t; mso-table-rspace: 0pt; color: #333; font-family: Arial, sans-serif; font=
-size: 14px; line-height: 20px; mso-line-height-rule: exactly; mso-text-rai=
se: 1px">=20
<tbody>=20
<tr>=20
<td id=3D"actions-pattern-container" valign=3D"middle" style=3D"padding: 0p=
x; border-collapse: collapse; padding: 15px 0 0 24px; vertical-align: middl=
e">=20
<table align=3D"left" style=3D"border-collapse: collapse; mso-table-lspace:=
 0pt; mso-table-rspace: 0pt; color: #333">=20
<tbody>=20
<tr>=20
<td class=3D"actions-pattern-action-icon-container" style=3D"padding: 0px; =
border-collapse: collapse; font-family: Arial, sans-serif; font-size: 14px;=
 line-height: 20px; mso-line-height-rule: exactly; mso-text-raise: 0px; ver=
tical-align: middle"><a href=3D"https://cwiki.apache.org/confluence/display=
/solr/Config&#43;API?src=3Dmail&amp;src.mail.timestamp=3D1460535327722&amp;=
src.mail.notification=3Dcom.atlassian.confluence.plugins.confluence-content=
-notifications-plugin%3Apage-edited-notification&amp;src.mail.recipient=3D8=
aa980874ebf4c1f0153f8e84cef212a&amp;src.mail.action=3Dview" title=3D"View p=
age Icon" style=3D"color: #3b73af; text-decoration: none"><img class=3D"act=
ions-pattern-action-icon-image" height=3D"16" width=3D"16" border=3D"0" tit=
le=3D"View page Icon" src=3D"cid:com.atlassian.confluence.plugins.confluenc=
e-email-resources%3Aview-page-email-adg-footer-item%3Aicon" alt=3D"View pag=
e Icon" style=3D"vertical-align: middle"></a></td>
<td class=3D"actions-pattern-action-text-container" style=3D"padding: 0px; =
border-collapse: collapse; font-family: Arial, sans-serif; font-size: 14px;=
 line-height: 20px; mso-line-height-rule: exactly; mso-text-raise: 4px; pad=
ding-left: 5px; white-space: nowrap"><a href=3D"https://cwiki.apache.org/co=
nfluence/display/solr/Config&#43;API?src=3Dmail&amp;src.mail.timestamp=3D14=
60535327722&amp;src.mail.notification=3Dcom.atlassian.confluence.plugins.co=
nfluence-content-notifications-plugin%3Apage-edited-notification&amp;src.ma=
il.recipient=3D8aa980874ebf4c1f0153f8e84cef212a&amp;src.mail.action=3Dview"=
 title=3D"View page" style=3D"color: #3b73af; text-decoration: none">View p=
age</a></td>
<td class=3D"actions-pattern-action-bull" style=3D"padding: 0px; border-col=
lapse: collapse; font-family: Arial, sans-serif; font-size: 14px; line-heig=
ht: 20px; mso-line-height-rule: exactly; mso-text-raise: 4px; color: #999; =
padding: 0 5px">=E2=80=A2</td>=20
</tr>=20
</tbody>=20
</table>=20
<table align=3D"left" style=3D"border-collapse: collapse; mso-table-lspace:=
 0pt; mso-table-rspace: 0pt; color: #333">=20
<tbody>=20
<tr>=20
<td class=3D"actions-pattern-action-icon-container" style=3D"padding: 0px; =
border-collapse: collapse; font-family: Arial, sans-serif; font-size: 14px;=
 line-height: 20px; mso-line-height-rule: exactly; mso-text-raise: 0px; ver=
tical-align: middle"><a href=3D"https://cwiki.apache.org/confluence/display=
/solr/Config&#43;API?showComments=3Dtrue&amp;showCommentArea=3Dtrue&amp;src=
=3Dmail&amp;src.mail.timestamp=3D1460535327722&amp;src.mail.notification=3D=
com.atlassian.confluence.plugins.confluence-content-notifications-plugin%3A=
page-edited-notification&amp;src.mail.recipient=3D8aa980874ebf4c1f0153f8e84=
cef212a&amp;src.mail.action=3Dcomment#addcomment" title=3D"Add comment Icon=
" style=3D"color: #3b73af; text-decoration: none"><img class=3D"actions-pat=
tern-action-icon-image" height=3D"16" width=3D"16" border=3D"0" title=3D"Ad=
d comment Icon" src=3D"cid:com.atlassian.confluence.plugins.confluence-emai=
l-resources%3Aadd-comment-to-content-email-adg-footer-item%3Aicon" alt=3D"A=
dd comment Icon" style=3D"vertical-align: middle"></a></td>
<td class=3D"actions-pattern-action-text-container" style=3D"padding: 0px; =
border-collapse: collapse; font-family: Arial, sans-serif; font-size: 14px;=
 line-height: 20px; mso-line-height-rule: exactly; mso-text-raise: 4px; pad=
ding-left: 5px; white-space: nowrap"><a href=3D"https://cwiki.apache.org/co=
nfluence/display/solr/Config&#43;API?showComments=3Dtrue&amp;showCommentAre=
a=3Dtrue&amp;src=3Dmail&amp;src.mail.timestamp=3D1460535327722&amp;src.mail=
.notification=3Dcom.atlassian.confluence.plugins.confluence-content-notific=
ations-plugin%3Apage-edited-notification&amp;src.mail.recipient=3D8aa980874=
ebf4c1f0153f8e84cef212a&amp;src.mail.action=3Dcomment#addcomment" title=3D"=
Add comment" style=3D"color: #3b73af; text-decoration: none">Add comment</a=
></td>
<td class=3D"actions-pattern-action-bull" style=3D"padding: 0px; border-col=
lapse: collapse; font-family: Arial, sans-serif; font-size: 14px; line-heig=
ht: 20px; mso-line-height-rule: exactly; mso-text-raise: 4px; color: #999; =
padding: 0 5px">=E2=80=A2</td>=20
</tr>=20
</tbody>=20
</table>=20
<table style=3D"border-collapse: collapse; mso-table-lspace: 0pt; mso-table=
-rspace: 0pt; color: #333">=20
<tbody>=20
<tr>=20
<td class=3D"actions-pattern-action-icon-container" style=3D"padding: 0px; =
border-collapse: collapse; font-family: Arial, sans-serif; font-size: 14px;=
 line-height: 20px; mso-line-height-rule: exactly; mso-text-raise: 0px; ver=
tical-align: middle"><a href=3D"https://cwiki.apache.org/confluence/plugins=
/likes/like.action?contentId=3D50857507&amp;src=3Dmail&amp;src.mail.timesta=
mp=3D1460535327722&amp;src.mail.notification=3Dcom.atlassian.confluence.plu=
gins.confluence-content-notifications-plugin%3Apage-edited-notification&amp=
;src.mail.recipient=3D8aa980874ebf4c1f0153f8e84cef212a&amp;src.mail.action=
=3Dlike" title=3D"Like Icon" style=3D"color: #3b73af; text-decoration: none=
"><img class=3D"actions-pattern-action-icon-image" height=3D"16" width=3D"1=
6" border=3D"0" title=3D"Like Icon" src=3D"cid:com.atlassian.confluence.plu=
gins.confluence-like%3Aview-email-adg-content-item%3Aicon" alt=3D"Like Icon=
" style=3D"vertical-align: middle"></a></td>
<td class=3D"actions-pattern-action-text-container" style=3D"padding: 0px; =
border-collapse: collapse; font-family: Arial, sans-serif; font-size: 14px;=
 line-height: 20px; mso-line-height-rule: exactly; mso-text-raise: 4px; pad=
ding-left: 5px; white-space: nowrap"><a href=3D"https://cwiki.apache.org/co=
nfluence/plugins/likes/like.action?contentId=3D50857507&amp;src=3Dmail&amp;=
src.mail.timestamp=3D1460535327722&amp;src.mail.notification=3Dcom.atlassia=
n.confluence.plugins.confluence-content-notifications-plugin%3Apage-edited-=
notification&amp;src.mail.recipient=3D8aa980874ebf4c1f0153f8e84cef212a&amp;=
src.mail.action=3Dlike" title=3D"Like" style=3D"color: #3b73af; text-decora=
tion: none">Like</a></td>=20
</tr>=20
</tbody>=20
</table> </td>=20
</tr>=20
</tbody>=20
</table> </td>=20
</tr>=20
<tr>=20
<td class=3D"email-content-rounded-bottom mobile-expand" style=3D"padding: =
0px; border-collapse: collapse; color: #fff; height: 5px; line-height: 5px;=
 padding: 0 15px 0 16px; background-color: #fff; border-bottom-right-radius=
: 5px; border-bottom-left-radius: 5px; border-top: 0; border-left: 1px soli=
d #ccc; border-bottom: 1px solid #ccc; border-right: 1px solid #ccc; mso-li=
ne-height-rule: exactly">&nbsp;</td>=20
</tr>=20
</tbody>=20
</table> </td>=20
</tr>=20
<tr>=20
<td id=3D"footer-pattern" style=3D"padding: 0px; border-collapse: collapse;=
 padding: 12px 20px">=20
<table id=3D"footer-pattern-container" cellspacing=3D"0" cellpadding=3D"0" =
border=3D"0" width=3D"100%" style=3D"border-collapse: collapse; mso-table-l=
space: 0pt; mso-table-rspace: 0pt; color: #333">=20
<tbody>=20
<tr>=20
<td id=3D"footer-pattern-links-container" width=3D"100%" style=3D"padding: =
0px; border-collapse: collapse; color: #999; font-size: 12px; line-height: =
18px; font-family: Arial, sans-serif; mso-line-height-rule: exactly; mso-te=
xt-raise: 2px">=20
<table align=3D"left" style=3D"border-collapse: collapse; mso-table-lspace:=
 0pt; mso-table-rspace: 0pt; color: #333; font-size: 12px; line-height: 18p=
x; font-family: Arial, sans-serif; mso-line-height-rule: exactly; mso-text-=
raise: 2px">=20
<tbody>=20
<tr>=20
<td class=3D"footer-pattern-links mobile-resize-text" style=3D"padding: 0px=
; border-collapse: collapse"><a href=3D"https://cwiki.apache.org/confluence=
/users/removespacenotification.action?spaceKey=3Dsolr&amp;src=3Dmail&amp;sr=
c.mail.timestamp=3D1460535327722&amp;src.mail.notification=3Dcom.atlassian.=
confluence.plugins.confluence-content-notifications-plugin%3Apage-edited-no=
tification&amp;src.mail.recipient=3D8aa980874ebf4c1f0153f8e84cef212a&amp;sr=
c.mail.action=3Dstop-watching" title=3D"" style=3D"color: #3b73af; text-dec=
oration: none">Stop watching space</a></td>
<td class=3D"footer-pattern-links-bull" style=3D"padding: 0px; border-colla=
pse: collapse; padding: 0 5px; color: #999">=E2=80=A2</td>=20
</tr>=20
</tbody>=20
</table>=20
<table style=3D"border-collapse: collapse; mso-table-lspace: 0pt; mso-table=
-rspace: 0pt; color: #333; font-size: 12px; line-height: 18px; font-family:=
 Arial, sans-serif; mso-line-height-rule: exactly; mso-text-raise: 2px">=20
<tbody>=20
<tr>=20
<td class=3D"footer-pattern-links mobile-resize-text" style=3D"padding: 0px=
; border-collapse: collapse"><a href=3D"https://cwiki.apache.org/confluence=
/users/editmyemailsettings.action?src=3Dmail&amp;src.mail.timestamp=3D14605=
35327722&amp;src.mail.notification=3Dcom.atlassian.confluence.plugins.confl=
uence-content-notifications-plugin%3Apage-edited-notification&amp;src.mail.=
recipient=3D8aa980874ebf4c1f0153f8e84cef212a&amp;src.mail.action=3Dmanage" =
title=3D"" style=3D"color: #3b73af; text-decoration: none">Manage notificat=
ions</a></td>=20
</tr>=20
</tbody>=20
</table> </td>
<td id=3D"footer-pattern-logo-desktop-container" rowspan=3D"2" valign=3D"to=
p" style=3D"padding: 0px; border-collapse: collapse; padding-left: 20px; ve=
rtical-align: top">=20
<table style=3D"border-collapse: collapse; mso-table-lspace: 0pt; mso-table=
-rspace: 0pt; color: #333">=20
<tbody>=20
<tr>=20
<td id=3D"footer-pattern-logo-desktop-padding" style=3D"padding: 0px; borde=
r-collapse: collapse; padding-top: 3px"><img id=3D"footer-pattern-logo-desk=
top" src=3D"cid:footer-desktop-logo" alt=3D"Confluence logo big" title=3D"C=
onfluence logo big" width=3D"132" height=3D"20" class=3D"image_fix"></td>=20
</tr>=20
</tbody>=20
</table> </td>=20
</tr>=20
<tr>=20
<td id=3D"footer-pattern-text" class=3D"mobile-resize-text" width=3D"100%" =
style=3D"padding: 0px; border-collapse: collapse; color: #999; font-size: 1=
2px; line-height: 18px; font-family: Arial, sans-serif; mso-line-height-rul=
e: exactly; mso-text-raise: 2px; display: none">This message was sent by At=
lassian Confluence 5.8.4<br> <img id=3D"footer-pattern-logo-mobile" src=3D"=
cid:footer-mobile-logo" alt=3D"" title=3D"" width=3D"0" height=3D"0" style=
=3D"display: none; mso-hide: all"></td>=20
</tr>=20
</tbody>=20
</table> </td>=20
</tr>=20
</tbody>=20
</table>=20
<table id=3D"sealed-section" border=3D"0" cellpadding=3D"0" cellspacing=3D"=
0" width=3D"0" style=3D"border-collapse: collapse; mso-table-lspace: 0pt; m=
so-table-rspace: 0pt; color: #333; display: none">=20
<tbody>=20
<tr>=20
<td style=3D"padding: 0px; border-collapse: collapse; border: 0; font-size:=
 0px; line-height: 0; mso-line-height-rule: exactly"></td>=20
</tr>=20
</tbody>=20
</table>
</body>
</html>=

------=_Part_1157937_100703508.1460535327916--"""

if __name__ == '__main__':
    unittest.main()
