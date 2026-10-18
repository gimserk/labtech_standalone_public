"""Render authenticated PBQ states and private test assets for offline browser checks."""
import base64
import io
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['DJANGO_SETTINGS_MODULE'] = 'app.test_settings'
import django
django.setup()
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from PIL import Image, ImageDraw
from app.pbq_test_helpers import PBQFixture
from app.pbq_models import PBQQuestion, PBQAnswerField
from app.pbq_artifacts import save_pbq_artifact
from app.pbq_services import publish_pbq, start_pbq_attempt, save_pbq_draft


class Fixture(PBQFixture, unittest.TestCase):
    pass


def main():
    call_command('migrate', verbosity=0, interactive=False)
    fixture = Fixture()
    fixture.setUp()
    try:
        activity = fixture.activity
        activity.title = 'Investigate a suspicious network connection'
        activity.scenario = '<p>A workstation contacted an unfamiliar host after a user opened an attachment. Review the evidence, identify the affected system, and explain how you would contain and investigate the incident.</p>'
        activity.save()
        fixture.question.prompt = '<p>Use the evidence to identify the incident and outline your first response.</p>'
        fixture.question.save()
        for index, title in enumerate(['Identify the affected host', 'Explain your evidence', 'Describe containment', 'Plan recovery'], start=2):
            question = PBQQuestion.objects.create(activity=activity, prompt='<p>'+title+'</p>', order=index)
            PBQAnswerField.objects.create(question=question, label=title, answer_type='short_answer',
                                          points=1, marking_guidance='Use the supplied evidence')
        image = Image.new('RGB', (720, 260), '#edf3fc')
        draw = ImageDraw.Draw(image)
        for x, label in [(20, 'Workstation'), (265, 'Firewall'), (510, 'External host')]:
            draw.rounded_rectangle((x, 70, x+180, 180), radius=12, fill='#172235')
            draw.text((x+20, 115), label, fill='white')
        draw.line((200, 125, 265, 125), fill='#0053ad', width=4)
        draw.line((445, 125, 510, 125), fill='#0053ad', width=4)
        output = io.BytesIO(); image.save(output, format='PNG')
        uploads = [
            ('network.png', output.getvalue(), 'image/png', 'Network overview'),
            ('events.log', b'09:42:17 workstation-17 opened attachment\n09:43:02 connection to 192.0.2.44:443\n<script>window.unsafeEvidence = true</script>', 'text/plain', 'Endpoint event log'),
            ('connections.csv', b'host,destination,port\nworkstation-17,192.0.2.44,443', 'text/csv', 'Network connections'),
            ('analyst.txt', b'The user reported an unexpected document prompt.\nPreserve evidence before making changes.', 'text/plain', 'Analyst notes'),
            ('timeline.txt', b'09:42 Attachment opened\n09:43 Outbound connection\n09:45 Alert received', 'text/plain', 'Incident timeline'),
        ]
        artifacts = []
        for index, (name, content, mime, title) in enumerate(uploads):
            artifacts.append(save_pbq_artifact(actor=fixture.teacher, activity=activity,
                upload=SimpleUploadedFile(name, content, content_type=mime),
                metadata={'title': title, 'alt_text': 'Workstation connected through a firewall to an external host', 'order': index}))
        activity = publish_pbq(actor=fixture.teacher, activity=activity)
        client = Client(); client.force_login(fixture.student)
        url = reverse('pbq_take', args=[fixture.course.pk, activity.pk])
        pages = {'start': client.get(url).content.decode()}
        attempt = start_pbq_attempt(user=fixture.student, activity=activity)
        pages['empty'] = client.get(url).content.decode()
        attempt = save_pbq_draft(user=fixture.student, attempt_id=attempt.pk, responses=fixture.answers, expected_revision=0)
        pages['saved'] = client.get(url).content.decode()
        pages['errors'] = client.post(url, {'action': 'submit', 'attempt_id': attempt.pk, 'revision': 1,
            **{'answer_'+key: value for key, value in fixture.answers.items()}}).content.decode()
        assets = {}
        for artifact in artifacts:
            asset_url = reverse('pbq_artifact', args=[fixture.course.pk, activity.pk, artifact.pk])
            if not artifact.is_image:
                asset_url += '?format=text'
            response = client.get(asset_url)
            assert response.status_code == 200
            body = b''.join(response.streaming_content) if response.streaming else response.content
            assets[asset_url] = {'contentType': response['Content-Type'], 'headers': dict(response.headers), 'body': base64.b64encode(body).decode()}
        client.force_login(fixture.teacher)
        pages['preview'] = client.get(reverse('pbq_preview', args=[fixture.course.pk, activity.pk])).content.decode()
        Path(sys.argv[1]).write_text(json.dumps({'pages': pages, 'assets': assets}))
        print('Rendered five PBQ states and five private artifacts')
    finally:
        fixture.doCleanups()


if __name__ == '__main__':
    main()
