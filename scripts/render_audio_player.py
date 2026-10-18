"""Render real student audio pages and a playable WAV for offline browser checks."""
import base64
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['DJANGO_SETTINGS_MODULE'] = 'app.test_settings'
import django
django.setup()
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, override_settings
from django.urls import reverse
from app.models import Audio, Chapter, Course, Enrollment


def main():
    call_command('migrate', verbosity=0, interactive=False)
    data = io.BytesIO()
    with wave.open(data, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(struct.pack('<h', 0) * 24000)
    body = data.getvalue()
    with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
        user = get_user_model().objects.create_user('audio-student')
        course = Course.objects.create(title='Incident response fundamentals')
        chapter = Chapter.objects.create(course=course, title='Investigate and respond', order=1)
        Enrollment.objects.create(user=user, course=course)
        common = dict(course=course, chapter=chapter, title='Listen: responding to a suspicious connection',
                      description='Review the evidence, containment options, and next steps.\nAfter listening, mark this lesson complete.')
        external = Audio.objects.create(**common, source_type='external_url',
            audio_url='https://media.example.test/lesson.wav?key=sample&version=2')
        uploaded = Audio(**common, source_type='upload', original_filename='incident-review.wav', content_type='audio/wav', file_size=len(body))
        uploaded.audio_file.save('incident-review.wav', SimpleUploadedFile('incident-review.wav', body), save=False)
        uploaded.save()
        client = Client()
        client.force_login(user)
        pages = {}
        for key, item in [('external', external), ('upload', uploaded)]:
            response = client.get(reverse('course_detail', args=[course.pk]), {'content':'audio', 'id':item.pk})
            assert response.status_code == 200
            pages[key] = response.content.decode()
        stream_url = reverse('labtech_stream_audio', args=[course.pk, uploaded.pk])
        stream = client.get(stream_url)
        assert b''.join(stream.streaming_content) == body
        Path(sys.argv[1]).write_text(json.dumps({'pages':pages, 'wav':base64.b64encode(body).decode(),
            'external_url':external.audio_url, 'stream_url':stream_url}))
        print('Rendered uploaded/external audio pages and verified authenticated WAV stream')


if __name__ == '__main__':
    main()
