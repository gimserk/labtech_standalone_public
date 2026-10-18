# app/management/commands/generate_course.py
import json
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

# Import the actual models from your models.py file
# Make sure to adjust 'core.models' if your models are in a different app
from app.models import Course, Chapter, TextPage, CourseCategory

# --- SIMULATED AI SERVICE (Replace with your actual AI client later) ---
def get_ai_course_blueprint(topic: str) -> str:
    """
    Simulates calling an AI to get the course structure.
    This function will be replaced with a real API call.
    """
    prompt = f"Design a beginner-level course outline for the topic '{topic}'. The course should have 3 sections (chapters), each with 2-3 lessons. The lessons should all be of type 'text'. Ensure the titles are practical and engaging. Output this as a valid JSON object."
    
    print("--- Sending Blueprint Prompt to AI ---")
    
    mock_response_json = f"""
    {{
      "course_title": "Introduction to {topic}",
      "category": "Information Technology",
      "chapters": [
        {{
          "chapter_title": "Chapter 1: The Absolute Basics",
          "lessons": [
            {{ "lesson_title": "What is a Network and Why Does It Matter?", "type": "text", "objective": "Define a computer network and its core purpose." }},
            {{ "lesson_title": "Key Components: Clients, Servers, and Peers", "type": "text", "objective": "Differentiate between network clients, servers, and peers." }}
          ]
        }},
        {{
          "chapter_title": "Chapter 2: How Data Travels",
          "lessons": [
            {{ "lesson_title": "Understanding IP Addresses", "type": "text", "objective": "Explain the function of an IP address." }},
            {{ "lesson_title": "The Role of Routers and Switches", "type": "text", "objective": "Describe how routers and switches direct traffic." }},
            {{ "lesson_title": "An Introduction to the OSI Model", "type": "text", "objective": "Briefly introduce the concept of networking layers." }}
          ]
        }},
        {{
          "chapter_title": "Chapter 3: Common Network Types",
          "lessons": [
            {{ "lesson_title": "LAN vs. WAN: Your Home and the World", "type": "text", "objective": "Compare and contrast Local Area Networks and Wide Area Networks." }},
            {{ "lesson_title": "The Magic of Wi-Fi", "type": "text", "objective": "Explain the basics of wireless networking." }}
          ]
        }}
      ]
    }}
    """
    return mock_response_json

def get_ai_text_page_content(title: str, objective: str) -> str:
    """
    Simulates calling an AI to generate the content for a text page.
    """
    prompt = f"Generate the content for a text page in an online course. The title is '{title}' and the learning objective is '{objective}'. The content should be comprehensive, easy to understand for a beginner, and formatted using HTML tags (e.g., <h3>, <p>, <ul>, <li>, <strong>)."
    
    print(f"--- Sending Content Prompt for: {title} ---")
    
    mock_response_html = f"""
    <h3>Overview</h3>
    <p>This lesson, titled '<strong>{title}</strong>,' is designed to help you {objective.lower()}. Understanding this concept is a fundamental building block for mastering the subject.</p>
    <hr>
    <h4>Key Points</h4>
    <ul>
        <li><strong>Point 1:</strong> This is the first key takeaway related to the objective.</li>
        <li><strong>Point 2:</strong> This is a second, equally important point.</li>
        <li><strong>Point 3:</strong> A final detail to round out your understanding.</li>
    </ul>
    <p><em>(This is auto-generated content. A real AI would provide detailed, relevant text here.)</em></p>
    """
    return mock_response_html

# --- END SIMULATED AI SERVICE ---

class Command(BaseCommand):
    help = 'Generates a full course structure and content using an AI model.'

    def add_arguments(self, parser):
        parser.add_argument('topic', type=str, help='The high-level topic for the new course.')

    @transaction.atomic
    def handle(self, *args, **options):
        topic = options['topic']
        self.stdout.write(self.style.SUCCESS(f"Starting course generation for topic: '{topic}'..."))

        # STAGE 1: Get the course blueprint from the AI
        self.stdout.write("1. Calling AI Architect for course blueprint...")
        try:
            blueprint_str = get_ai_course_blueprint(topic)
            blueprint = json.loads(blueprint_str)
        except json.JSONDecodeError:
            self.stderr.write(self.style.ERROR("Failed to parse JSON blueprint from AI. Aborting."))
            return

        # STAGE 2: Create the main Course object
        self.stdout.write("2. Creating Course object in the database...")
        category_name = blueprint.get('category', 'Uncategorized')
        category, _ = CourseCategory.objects.get_or_create(
            name=category_name, 
            defaults={'slug': slugify(category_name)}
        )

        new_course = Course.objects.create(
            title=blueprint['course_title'],
            description=f"An AI-generated course on {topic}. Covers fundamental concepts and practical knowledge.",
            category=category,
            is_public=False,
            is_active=False
        )
        self.stdout.write(self.style.SUCCESS(f"   -> Created Course: '{new_course.title}' (ID: {new_course.id})"))

        # STAGE 3: Loop through chapters and lessons
        self.stdout.write("3. Generating chapters, lessons, and content...")
        chapter_order = 1
        lesson_order = 1
        for chapter_data in blueprint.get('chapters', []):
            new_chapter = Chapter.objects.create(
                course=new_course,
                title=chapter_data['chapter_title'],
                order=chapter_order
            )
            self.stdout.write(f"   -> Created Chapter: '{new_chapter.title}'")

            for lesson_data in chapter_data.get('lessons', []):
                if lesson_data['type'] == 'text':
                    content_html = get_ai_text_page_content(lesson_data['lesson_title'], lesson_data['objective'])
                    
                    TextPage.objects.create(
                        course=new_course,
                        chapter=new_chapter,
                        title=lesson_data['lesson_title'],
                        content=content_html,
                        order=lesson_order
                    )
                    self.stdout.write(f"     - Created TextPage: '{lesson_data['lesson_title']}'")
                    lesson_order += 1
            
            chapter_order += 1
            lesson_order = 1

        self.stdout.write(self.style.SUCCESS("\nCourse generation complete! The new course has been created as a draft."))