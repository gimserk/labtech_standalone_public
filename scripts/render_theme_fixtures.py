"""Render real application pages against an isolated in-memory test database.

Run from the repository root: python scripts/render_theme_fixtures.py OUTPUT.json
The browser check serves these pages and local dependencies without a live server.
"""
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["DJANGO_SETTINGS_MODULE"] = "app.test_settings"
import django

django.setup()
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from app.models import (CodingActivity, Flashcard, FlashcardDeck, Quiz, Conversation, Lab, TextPage, CyberCityESP32, CourseResource,
                        Message, SupportTicket, HotspotActivity, Label,
                        DragAndDropActivity, DragAndDropLabel, CyberCity, CyberCityBuilding)
from app.pbq_test_helpers import PBQFixture


class Fixture(PBQFixture, unittest.TestCase):
    pass


def main():
    call_command("migrate", verbosity=0, interactive=False)
    fixture = Fixture()
    fixture.setUp()
    try:
        fixture.teacher.is_superuser = True
        fixture.teacher.is_staff = True
        fixture.teacher.save()
        fixture.course.is_active = True
        fixture.course.save()
        lesson = TextPage.objects.create(
            course=fixture.course, chapter=fixture.chapter,
            title="Safety overview", content="<p>Review the lab rules.</p>"
        )
        deck = FlashcardDeck.objects.create(
            course=fixture.course, chapter=fixture.chapter, title="Networking review"
        )
        Flashcard.objects.create(deck=deck, term="Firewall", definition="Filters traffic, enforces policy.")
        quiz = Quiz.objects.create(course=fixture.course, chapter=fixture.chapter, title="Review quiz")
        coding = CodingActivity.objects.create(
            course=fixture.course, chapter=fixture.chapter, title="Python exercise",
            description="<p>Print a greeting.</p>", starter_code='print("Hello")'
        )
        lab = Lab.objects.create(course=fixture.course, chapter=fixture.chapter, title='Persistent practice', clone_type='full')
        CourseResource.objects.create(
            course=fixture.course, title="Security Study Guide",
            category=CourseResource.CATEGORY_SYLLABUS,
            file="course_resources/theme-study-guide.pdf", visible_to_students=True,
            uploaded_by=fixture.teacher,
        )
        CourseResource.objects.create(
            course=fixture.course, title="Wireshark Slides",
            category=CourseResource.CATEGORY_SLIDE_DECK,
            file="course_resources/theme-packets.pptx", visible_to_students=True,
            uploaded_by=fixture.teacher,
        )
        conversation = Conversation.objects.create(course=fixture.course, subject="Lab questions")
        conversation.participants.add(fixture.teacher, fixture.student)
        Message.objects.create(conversation=conversation, author=fixture.student, content="<p>Please review my lab.</p>")
        Message.objects.create(conversation=conversation, author=fixture.teacher, content="<p>Review the instructions.</p>")
        ticket = SupportTicket.objects.create(user=fixture.teacher, subject="Access to lab", description="<p>Test request</p>")
        hotspot = HotspotActivity.objects.create(course=fixture.course, chapter=fixture.chapter,
            title="Label a network", scenario="<p>Connect each label.</p>", background_image="theme-test-network.png")
        Label.objects.create(activity=hotspot, text="Router")
        drag = DragAndDropActivity.objects.create(course=fixture.course, chapter=fixture.chapter,
            title="Arrange a network", scenario="<p>Place each label.</p>", background_image="theme-test-network.png")
        DragAndDropLabel.objects.create(activity=drag, text="Switch")
        city = CyberCity.objects.create(name="Training city", is_public=True)
        building = CyberCityBuilding.objects.create(cybercity=city, name="Hospital")
        esp = CyberCityESP32.objects.create(
            building=building, name="Wall Display",
            mac_address="AA:BB:CC:22:44:77"
        )
        client = Client()
        client.force_login(fixture.teacher)
        c, a = fixture.course.pk, fixture.activity.pk
        routes = [
            ("home", []), ("profile_edit", []), ("inbox", []),
            ("my_tickets", []), ("create_ticket", []),
            ("conversation_view", [conversation.pk]), ("ticket_detail", [ticket.pk]),
            ("help_desk_portal", []), ("manage_faq_categories", []),
            ("labtech_manage_proxmox_servers_list", []),
            ("labtech_add_proxmox_server", []), ("course_catalog", []),
            ("instructor_my_courses", []), ("labtech_manage_course_content", [c]),
            ("ai_improve_course_content", [c, "textpage", lesson.pk]),
            ("labtech_add_lab", [c]), ("labtech_edit_lab", [c, lab.pk]),
            ("labtech_edit_course", [c]), ("bulk_update_content_dates", [c]),
            ("course_detail", [c]), ("instructor_gradebook", [c]),
            ("labtech_add_question_to_quiz", [c, quiz.pk]),
            ("learn_flashcard_deck", [c, deck.pk]),
            ("review_flashcard_deck", [c, deck.pk]),
            ("import_flashcards_csv", [c, deck.pk]),
            ("take_coding_activity", [c, coding.pk]),
            ("take_hotspot_activity", [c, hotspot.pk]), ("labtech_manage_hotspot", [c, hotspot.pk]),
            ("take_drag_and_drop_activity", [c, drag.pk]), ("labtech_manage_drag_and_drop", [c, drag.pk]),
            ("cybercity_dashboard", []), ("cybercity_add", []),
            ("cybercity_detail", [city.pk]), ("cybercity_building_detail", [city.pk, building.pk]),
            ("cybercity_esp32_detail", [city.pk, building.pk, esp.pk]),
            ("cybercity_soc_dashboard", [city.pk]),
            ("cybercity_visualizer", [city.pk]), ("student_cybercity_visualizer", [city.pk]),
            ("pbq_edit", [c, a]), ("pbq_manage", [c, a]), ("pbq_preview", [c, a]),
        ]
        pages = {}
        for name, args in routes:
            response = client.get(reverse(name, args=args))
            if response.status_code != 200:
                raise AssertionError(f"{name}: HTTP {response.status_code}")
            pages[name] = response.content.decode()
        # Verify both staff workspaces in the browser's existing four-theme matrix.
        instructor_response = client.get(reverse("home"), {"view_as": "instructor"})
        if instructor_response.status_code != 200:
            raise AssertionError(f"home_instructor: HTTP {instructor_response.status_code}")
        pages["home_instructor"] = instructor_response.content.decode()
        # Exercise all shared Bootstrap status roles, even if the sample records
        # don't happen to use a particular status on the real pages above.
        from django.template import engines
        from django.test import RequestFactory
        request = RequestFactory().get('/')
        request.user = fixture.teacher
        request.session = client.session
        components = '<h1>Shared controls</h1>'
        for role in ['primary', 'secondary', 'success', 'danger', 'info', 'warning']:
            components += f'<p><button class="btn btn-{role}">{role} action</button> <button class="btn btn-outline-{role}">Outline {role}</button> <span class="badge bg-{role}">{role} status</span></p>'
            if role in ['primary', 'secondary', 'success', 'danger', 'info', 'warning']:
                components += f'<div class="alert alert-{role}">{role} message <a class="alert-link" href="#">Details</a></div>'
        components += '<label for="sample-input">Example input</label><input id="sample-input" class="form-control" placeholder="Example placeholder"><p class="text-muted">Supporting information</p>'
        pages['shared_controls'] = engines['django'].from_string(
            '{% extends "labtech/generic_base.html" %}{% block labtech_content %}' + components + '{% endblock %}'
        ).render({'user': fixture.teacher}, request)
        Path(sys.argv[1]).write_text(json.dumps(pages))
        print(f"Rendered {len(pages)} real application pages")
    finally:
        fixture.doCleanups()


if __name__ == "__main__":
    main()
