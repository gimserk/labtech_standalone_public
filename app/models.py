from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.urls import reverse
import datetime
import uuid
from django.db import transaction
from django.db.models import Max, Count
from django.utils.text import slugify # For generating slugs
from ckeditor.fields import RichTextField
from ckeditor_uploader.fields import RichTextUploadingField # If using image uploads in editor
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from payments.models import BasePayment
from ckeditor_uploader.fields import RichTextUploadingField
from .validators import validate_safe_file

from django.db import models
from django.core.exceptions import ValidationError

class ProxmoxServer(models.Model):
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="A friendly name for this Proxmox server/cluster connection (e.g., 'Main Datacenter PVE')"
    )
    host = models.CharField(max_length=255, help_text="Hostname or IP address of the Proxmox server.")
    port = models.PositiveIntegerField(default=8006, help_text="Proxmox API port (default is 8006).")
    user = models.CharField(max_length=100, help_text="Proxmox user (e.g., 'root@pam' or 'your_api_user@pve').")
    password_or_token_secret = models.CharField(max_length=255, help_text="Password for the user or the API token's secret value.")
    api_token_id = models.CharField(max_length=255, blank=True, null=True, help_text="API Token ID (e.g., 'terraform@pve!mytoken'). If using token-based auth, user might be 'terraform@pve'.")
    verify_ssl = models.BooleanField(default=True, help_text="Verify SSL certificate. Set to False for self-signed certs in dev/test only.")
    vnc_port_start = models.PositiveIntegerField(default=5900, help_text="The starting port number for VNC allocation (e.g., 5900).")
    vnc_port_end = models.PositiveIntegerField(default=5999, help_text="The ending port number for VNC allocation (e.g., 5999).")
    is_default = models.BooleanField(default=False, help_text="Is this the default Proxmox server to use for new labs?")
    assigned_guacamole_server = models.ForeignKey(
        'GuacamoleServer',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='proxmox_assignments',
        help_text="The primary Guacamole server that provides remote connections for this Proxmox host."
    )
    shared_storage = models.CharField(
        max_length=100,
        blank=True,
        help_text="Name of the shared storage (e.g., ceph-images, nfs-vmstore) visible on all target nodes."
    )
    PLACEMENT_MANUAL = 'manual'
    PLACEMENT_LEAST = 'least_loaded'
    PLACEMENT_CHOICES = [
        (PLACEMENT_LEAST, 'Least loaded (by VM count)'),
        (PLACEMENT_MANUAL, 'Manual (always place on default_manual_node)'),
    ]
    placement_strategy = models.CharField(
        max_length=20,
        choices=PLACEMENT_CHOICES,
        default=PLACEMENT_LEAST,
        help_text="How to choose a node when cloning."
    )
    allowed_nodes = models.TextField(
        blank=True,
        help_text="Optional: comma-separated node names to allow (e.g., pve1,pve2). Leave blank to allow all online nodes."
    )
    default_manual_node = models.CharField(
        max_length=100,
        blank=True,
        help_text="If strategy is Manual, place all clones on this node."
    )
    cluster_domain = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional: The domain suffix for your cluster nodes (e.g., 'lab.local'). Do not include the leading dot."
    )
    vmid_range_start = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="The starting VMID for the assignable pool on this server (e.g., 1000)."
    )
    vmid_range_end = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="The ending VMID for the assignable pool on this server (e.g., 1999)."
    )
    last_sync_status = models.TextField(blank=True, null=True, editable=False, help_text="Status of the last template sync attempt.")
    last_successful_sync = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def allowed_nodes_list(self):
        if not self.allowed_nodes:
            return []
        return [n.strip() for n in self.allowed_nodes.split(',') if n.strip()]

    def clean(self):
        super().clean()
        if self.placement_strategy == self.PLACEMENT_MANUAL:
            if not self.default_manual_node:
                raise ValidationError("default_manual_node is required when placement_strategy is Manual.")
            if self.allowed_nodes and self.default_manual_node not in self.allowed_nodes_list():
                raise ValidationError("default_manual_node must be included in allowed_nodes when provided.")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_default:
            ProxmoxServer.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Proxmox Server Connection"
        verbose_name_plural = "Proxmox Server Connections"

class ProxmoxVMTemplate(models.Model):
    proxmox_server = models.ForeignKey(ProxmoxServer, on_delete=models.CASCADE, related_name='vm_templates')
    vmid = models.PositiveIntegerField(help_text="VM/CT ID of the template in Proxmox.")
    node = models.CharField(max_length=100, help_text="Proxmox node where the template resides.")
    name = models.CharField(max_length=255, help_text="Name of the template as it appears in Proxmox.")
    storage = models.CharField(max_length=100, help_text="Storage location of the template in Proxmox.")
    template_type = models.CharField(max_length=10, choices=[('qemu', 'QEMU (VM)'), ('lxc', 'LXC (Container)')], default='qemu')
    last_synced = models.DateTimeField(auto_now=True)
    description = models.TextField(blank=True, null=True, help_text="A manual description of the template's purpose and contents.")
    
    internet_access = models.BooleanField(default=False, help_text="Does this template have direct internet access configured?")
    cpu_cores = models.PositiveIntegerField(null=True, blank=True)
    memory_mb = models.PositiveIntegerField(null=True, blank=True, help_text="RAM in MB.")
    disk_gb = models.PositiveIntegerField(null=True, blank=True, help_text="Primary disk size in GB.")
    iso_info = models.CharField(max_length=255, null=True, blank=True, help_text="Name of the attached ISO, if any.")
    network_mode = models.CharField(max_length=50, null=True, blank=True, help_text="DHCP or static IP configuration.")
    static_ip_config = models.CharField(max_length=255, null=True, blank=True, help_text="Static IP address, if configured.")
    
    is_active_for_labs = models.BooleanField(default=True, help_text="Can this template be used to create new labs?")

    class Meta:
        unique_together = ('proxmox_server', 'node', 'vmid')
        verbose_name = "Proxmox VM/CT Template"
        verbose_name_plural = "Proxmox VM/CT Templates"
        ordering = ['proxmox_server', 'name']

    def __str__(self):
        return f"{self.name} (Node: {self.node}, VMID: {self.vmid})"
    
class CourseCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, help_text="URL-friendly version of the name.")
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Course Category"
        verbose_name_plural = "Course Categories"
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug: # Auto-generate slug if not provided
            self.slug = slugify(self.name)
            # Ensure slug uniqueness
            original_slug = self.slug
            counter = 1
            # Check against other instances, excluding self if this instance already exists (pk is not None)
            queryset = CourseCategory.objects.filter(slug=self.slug)
            if self.pk:
                queryset = queryset.exclude(pk=self.pk)
            while queryset.exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
                queryset = CourseCategory.objects.filter(slug=self.slug) # Re-evaluate queryset with new slug
                if self.pk:
                    queryset = queryset.exclude(pk=self.pk)

        super().save(*args, **kwargs)

def generate_enrollment_code():
    """Generates a unique 8-character enrollment code."""
    return str(uuid.uuid4().hex)[:8].upper()

# In app/models.py

class Course(models.Model):
    title = models.CharField(max_length=255, help_text="Title of the course.")
    description = models.TextField(blank=True, help_text="Detailed description of the course.")
    category = models.ForeignKey(
        CourseCategory,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='courses',
        help_text="The primary category this course falls under."
    )
    thumbnail = models.ImageField(
        upload_to='course_thumbnails/',
        null=True, blank=True,
        help_text="A representative image for the course."
    )
    instructors = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='courses_taught',
        blank=True,
        help_text="Instructors assigned to this course."
    )
    
    # --- NEW ENROLLMENT FIELDS ---
    ENROLLMENT_OPEN = 'open'
    ENROLLMENT_CODE = 'code'
    ENROLLMENT_CHOICES = [
        (ENROLLMENT_OPEN, 'Open Enrollment (anyone can join)'),
        (ENROLLMENT_CODE, 'Code Required (students must enter a code to join)'),
    ]
    enrollment_type = models.CharField(
        max_length=10,
        choices=ENROLLMENT_CHOICES,
        default=ENROLLMENT_OPEN,
        help_text="Choose how students can enroll in this course."
    )
    enrollment_code = models.CharField(
        max_length=8,
        unique=True,
        blank=True, null=True,
        help_text="A unique 8-character code for enrollment. Auto-generated if code-required."
    )
    # --- END NEW FIELDS ---
    
    is_active = models.BooleanField(default=True, help_text="Is the course currently active and available for enrollment/access?")
    is_archived = models.BooleanField(default=False, help_text="Archived courses are hidden from main lists but not deleted.")
    estimated_duration = models.CharField(max_length=100, blank=True, help_text="e.g., 'Approx. 4 weeks', '10-12 hours'")
    DIFFICULTY_BEGINNER = 'beginner'
    DIFFICULTY_INTERMEDIATE = 'intermediate'
    DIFFICULTY_ADVANCED = 'advanced'
    DIFFICULTY_CHOICES = [
        (DIFFICULTY_BEGINNER, 'Beginner'),
        (DIFFICULTY_INTERMEDIATE, 'Intermediate'),
        (DIFFICULTY_ADVANCED, 'Advanced'),
    ]
    difficulty_level = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default=DIFFICULTY_BEGINNER, blank=True)
    available_from = models.DateTimeField(null=True, blank=True, help_text="The date this course becomes available to students.")
    due_date = models.DateTimeField(null=True, blank=True, help_text="An optional overall due date for the course.")
    available_until = models.DateTimeField(null=True, blank=True, help_text="The date this course is no longer available.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.enrollment_type == self.ENROLLMENT_CODE and not self.enrollment_code:
            # Generate a new unique code
            while True:
                code = generate_enrollment_code()
                if not Course.objects.filter(enrollment_code=code).exists():
                    self.enrollment_code = code
                    break
        elif self.enrollment_type == self.ENROLLMENT_OPEN:
            self.enrollment_code = None
        super().save(*args, **kwargs)
        
    def text_page_count(self): return self.text_pages.count()
    def video_count(self): return self.videos.count()
    def audio_count(self): return self.audio_items.count()
    def quiz_count(self): return self.quizzes.count()
    def pbq_activity_count(self): return self.pbq_activities.count()
    def lab_count(self): return self.labs.count()
    def flashcard_deck_count(self): return self.flashcard_decks.count()
    def hotspot_activity_count(self): return self.hotspot_activities.count()
    def drag_and_drop_activity_count(self): return self.drag_and_drop_activities.count()
    def coding_activity_count(self): return self.coding_activities.count()
    def scenario_activity_count(self): return self.scenario_activities.count()

    class Meta:
        verbose_name = "Course"
        verbose_name_plural = "Courses"
        ordering = ['title']

class ContentTiming(models.Model):
    """An abstract model to add availability and due dates to course content."""
    available_from = models.DateTimeField(null=True, blank=True, help_text="When this item becomes available to students.")
    due_date = models.DateTimeField(null=True, blank=True, help_text="Optional due date for this item.")
    available_until = models.DateTimeField(null=True, blank=True, help_text="When this item is no longer available to students.")

    class Meta:
        abstract = True

class Enrollment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='enrollments',
        help_text="The user enrolled in the course."
    )
    course = models.ForeignKey(
        'Course',
        on_delete=models.CASCADE,
        related_name='enrollments',
        help_text="The course the user is enrolled in."
    )
    enrollment_date = models.DateTimeField(auto_now_add=True, help_text="Date and time of enrollment.")

    class Meta:
        unique_together = ('user', 'course')
        ordering = ['-enrollment_date']
        verbose_name = "Enrollment"
        verbose_name_plural = "Enrollments"

    def __str__(self):
        return f"{self.user.username} enrolled in {self.course.title}"

class Chapter(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='chapters')
    title = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0, help_text="The order of the chapter within the course.")
    
    class Meta:
        ordering = ['order']
        unique_together = ('course', 'order')
        
    def __str__(self):
        return f"Chapter {self.order}: {self.title}"

class QuestionBank(models.Model):
    """A bank of questions belonging to a course, for use in multiple quizzes."""
    course = models.OneToOneField(Course, on_delete=models.CASCADE, related_name='question_bank')

    def __str__(self):
        return f"Question Bank for {self.course.title}"

class TextPage(ContentTiming):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='text_pages')
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='text_pages', null=True, blank=True)
    title = models.CharField(max_length=255)
    content = RichTextUploadingField(help_text="Use the editor to format your content, add images, and more.")
    order = models.PositiveIntegerField(default=0, help_text="Order of this page within the course's text pages.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['course', 'chapter__order', 'order']
        verbose_name = "Text Page (Course Content)"
        verbose_name_plural = "Text Pages (Course Content)"

    def __str__(self):
        return f"{self.title} (Course: {self.course.title})"

def audio_upload_path(instance, filename):
    """Never use a submitted filename as a storage key."""
    import os
    return f"course_audio/{instance.course_id}/{uuid.uuid4().hex}{os.path.splitext(filename)[1].lower()}"


class Audio(ContentTiming):
    UPLOAD = 'upload'
    EXTERNAL_URL = 'external_url'
    SOURCE_CHOICES = ((UPLOAD, 'Upload'), (EXTERNAL_URL, 'External HTTPS URL'))

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='audio_items')
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='audio_items', null=True, blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    audio_file = models.FileField(upload_to=audio_upload_path, blank=True)
    audio_url = models.URLField(max_length=1000, blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=100, blank=True)
    file_size = models.PositiveBigIntegerField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['course', 'chapter__order', 'order']
        constraints = [models.CheckConstraint(
            condition=(models.Q(source_type='upload', audio_file__gt='', audio_url='') |
                       models.Q(source_type='external_url', audio_file='', audio_url__gt='')),
            name='audio_exactly_one_source',
        )]

    def clean(self):
        from django.core.exceptions import ValidationError
        from .audio_content import validate_external_url
        errors = {}
        if self.chapter_id and self.course_id and self.chapter.course_id != self.course_id:
            errors['chapter'] = 'Choose a chapter in this course.'
        if self.source_type == self.UPLOAD:
            if not self.audio_file or self.audio_url:
                errors['audio_file'] = 'Provide an upload and no URL.'
        elif self.source_type == self.EXTERNAL_URL:
            if not self.audio_url or self.audio_file:
                errors['audio_url'] = 'Provide a URL and no upload.'
            elif not errors:
                try:
                    validate_external_url(self.audio_url)
                except ValidationError as exc:
                    errors['audio_url'] = exc
        else:
            errors['source_type'] = 'Choose a source.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.title} (Course: {self.course.title})'


@receiver(post_delete, sender=Audio)
def cleanup_deleted_audio(sender, instance, **kwargs):
    if instance.audio_file:
        from .audio_content import delete_owned_file
        storage, name = instance.audio_file.storage, instance.audio_file.name
        transaction.on_commit(lambda: delete_owned_file(storage, name, instance.pk, instance.course_id))


class Video(ContentTiming):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='videos')
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='videos', null=True, blank=True)
    title = models.CharField(max_length=255)
    PLATFORM_YOUTUBE = 'youtube'
    PLATFORM_VIMEO = 'vimeo'
    PLATFORM_SELF_HOSTED = 'self_hosted'
    PLATFORM_CHOICES = [
        (PLATFORM_YOUTUBE, 'YouTube'),
        (PLATFORM_VIMEO, 'Vimeo'),
        (PLATFORM_SELF_HOSTED, 'Self-hosted URL'),
    ]
    video_platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, default=PLATFORM_YOUTUBE)
    video_id_or_url = models.CharField(max_length=500, help_text="YouTube/Vimeo Video ID, or full URL for self-hosted.")
    description = models.TextField(blank=True, help_text="Optional description for the video.")
    order = models.PositiveIntegerField(default=0, help_text="Order of this video within the course's videos.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['course', 'chapter__order', 'order']
        verbose_name = "Video (Course Content)"
        verbose_name_plural = "Videos (Course Content)"

    def get_embed_url(self):
        if self.video_platform == self.PLATFORM_YOUTUBE:
            return f"https://www.youtube.com/embed/{self.video_id_or_url}" # Corrected URL
        elif self.video_platform == self.PLATFORM_VIMEO:
            return f"https://player.vimeo.com/video/{self.video_id_or_url}"
        elif self.video_platform == self.PLATFORM_SELF_HOSTED:
            return self.video_id_or_url
        return None

    def __str__(self):
        return f"{self.title} (Course: {self.course.title})"

class Quiz(ContentTiming):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='quizzes')
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='quizzes', null=True, blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0, help_text="Order of this quiz within the course's quizzes.")
    pass_mark_percentage = models.PositiveIntegerField(default=70, help_text="Percentage required to pass this quiz.")
    is_published = models.BooleanField(default=False)
    max_attempts = models.PositiveIntegerField(
        default=0,
        help_text="Maximum number of attempts allowed. Set to 0 for unlimited."
    )
    shuffle_questions = models.BooleanField(
        default=False,
        help_text="If checked, the order of questions will be randomized for each attempt."
    )
    shuffle_answers = models.BooleanField(
        default=False,
        help_text="If checked, the order of choices for multiple-choice questions will be randomized."
    )
    SHOW_ANSWERS_NEVER = 'never'
    SHOW_ANSWERS_AFTER_ATTEMPT = 'attempt'
    SHOW_ANSWERS_AFTER_DUE_DATE = 'due_date'
    SHOW_ANSWERS_AFTER_UNTIL_DATE = 'until_date'
    SHOW_ANSWERS_CHOICES = [
        (SHOW_ANSWERS_NEVER, 'Never'),
        (SHOW_ANSWERS_AFTER_ATTEMPT, 'Immediately after each attempt'),
        (SHOW_ANSWERS_AFTER_DUE_DATE, 'After the Due Date passes'),
        (SHOW_ANSWERS_AFTER_UNTIL_DATE, 'After the content availability ends'),
    ]
    show_answers_after = models.CharField(
        max_length=15,
        choices=SHOW_ANSWERS_CHOICES,
        default=SHOW_ANSWERS_NEVER,
        help_text="Controls when students can see the correct answers."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['course', 'chapter__order', 'order']
        verbose_name = "Quiz (Course Content)"
        verbose_name_plural = "Quizzes (Course Content)"

    def __str__(self):
        return f"{self.title} (Course: {self.course.title})"

class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question_bank = models.ForeignKey(QuestionBank, on_delete=models.SET_NULL, related_name='questions', null=True, blank=True)
    text = models.TextField(help_text="The question text.")
    TYPE_MULTIPLE_CHOICE = 'MCQ'
    TYPE_TRUE_FALSE = 'TF'
    TYPE_SHORT_ANSWER = 'SA'
    QUESTION_TYPE_CHOICES = [
        (TYPE_MULTIPLE_CHOICE, 'Multiple Choice'),
        (TYPE_TRUE_FALSE, 'True/False'),
        (TYPE_SHORT_ANSWER, 'Short Answer'),
    ]
    question_type = models.CharField(max_length=3, choices=QUESTION_TYPE_CHOICES, default=TYPE_MULTIPLE_CHOICE)
    order = models.PositiveIntegerField(default=0, help_text="Order of this question within the quiz.")
    points = models.PositiveIntegerField(default=1, help_text="Points awarded for a correct answer.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['quiz', 'order']
        verbose_name = "Quiz Question"
        verbose_name_plural = "Quiz Questions"

    def __str__(self):
        return f"Q{self.order}: {self.text[:50]}... (Quiz: {self.quiz.title})"

class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=500, help_text="The text for this answer choice.")
    is_correct = models.BooleanField(default=False, help_text="Is this the correct answer?")

    def __str__(self):
        return f"{self.text} (Correct: {self.is_correct})"

    class Meta:
        ordering = ['question', 'id']
        verbose_name = "Answer Choice"
        verbose_name_plural = "Answer Choices"

class Lab(ContentTiming):
    title = models.CharField(max_length=255, help_text="Title of the lab.")
    description = models.TextField(blank=True, help_text="Description or objectives of the lab.")
    course = models.ForeignKey(
        'Course', # Using string to avoid import errors if defined later
        on_delete=models.CASCADE,
        related_name='labs', 
        help_text="The course this lab belongs to."
    )
    chapter = models.ForeignKey(
        'Chapter', # Using string to avoid import errors
        on_delete=models.CASCADE, 
        related_name='labs', 
        null=True, 
        blank=True
    )
    order = models.PositiveIntegerField(default=0, help_text="Order of this lab within the chapter.")
    is_published = models.BooleanField(default=False, help_text="Is this lab visible to students?")
    
    # Lab Type and Duration Constants
    TYPE_PERSISTENT = 'persistent'
    TYPE_TIMED = 'timed'
    LAB_TYPE_CHOICES = [
        (TYPE_PERSISTENT, 'Persistent (Never ends until manually stopped/deleted)'),
        (TYPE_TIMED, 'Timed (Automatically deleted after duration)'),
    ]

    # Lab Type and Duration Fields
    lab_type = models.CharField(
        max_length=15,
        choices=LAB_TYPE_CHOICES,
        default=TYPE_PERSISTENT,
        help_text="Determines if the lab instance is persistent or timed."
    )
    CLONE_LINKED = 'linked'
    CLONE_FULL = 'full'
    CLONE_TYPE_CHOICES = [
        (CLONE_LINKED, 'Linked Clone'),
        (CLONE_FULL, 'Full Clone'),
    ]
    clone_type = models.CharField(
        max_length=6,
        choices=CLONE_TYPE_CHOICES,
        default=CLONE_LINKED,
        help_text=(
            "Linked clones are faster and use less storage, but depend on the source template "
            "and require storage that supports linked clones. Full clones take longer to create "
            "and use more storage because all disk data is copied. They are independent of the "
            "source template and may be better for persistent labs used over a long period. "
            "This choice applies to every machine cloned for this lab. Changing it does not "
            "convert existing virtual machines."
        ),
    )
    duration_minutes = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Duration in minutes for timed labs. Leave blank for persistent labs."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """
        Custom model validation to ensure that timed labs have a duration
        and persistent labs do not.
        """
        super().clean()
        if self.lab_type == self.TYPE_TIMED and not self.duration_minutes:
            raise ValidationError({'duration_minutes': "Duration must be set for timed labs."})
        if self.lab_type == self.TYPE_PERSISTENT and self.duration_minutes:
            raise ValidationError({'duration_minutes': "Duration should not be set for persistent labs. Leave blank."})

    class Meta:
        ordering = ['chapter__order', 'order', 'title']
        verbose_name = "Lab (Course Content)"
        verbose_name_plural = "Labs (Course Content)"

    def __str__(self):
        return f"{self.title} (Course: {self.course.title})"

class LabMachine(models.Model):
    GUEST_OS_LINUX = 'linux'
    GUEST_OS_WINDOWS = 'windows'
    GUEST_OS_CHOICES = [(GUEST_OS_LINUX, 'Linux'), (GUEST_OS_WINDOWS, 'Windows')]
    guest_os = models.CharField(max_length=8, choices=GUEST_OS_CHOICES, null=True, blank=True)
    """
    Defines a type of machine to be included in a lab. A lab can have multiple machines.
    """
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, related_name='machines')
    name = models.CharField(max_length=100, help_text="A unique, descriptive name for this machine within the lab (e.g., 'WebServer', 'Database', 'AttackerPC').")
    
    proxmox_vm_template = models.ForeignKey(
        'ProxmoxVMTemplate',
        on_delete=models.SET_NULL,
        null=True,
        related_name='lab_machines',
        help_text="The Proxmox VM/CT template to be cloned for this machine."
    )
    is_isolated = models.BooleanField(
        default=False,
        help_text="Block all network traffic to and from this machine. Overrides all other settings if checked."
    )
    can_access_lab_resources = models.BooleanField(
        default=True,
        help_text="Default. Allows communication with other machines within this same lab instance."
    )
    can_access_internet = models.BooleanField(
        default=False,
        help_text="Allow this machine to access the public internet."
    )
    can_access_cybercity = models.BooleanField(
        default=False,
        help_text="Allow this machine to access the institution's primary CyberCity network."
    )
    order = models.PositiveIntegerField(default=0, help_text="The order this machine will be displayed in the lab.")
    username = models.CharField(
        max_length=100, 
        blank=True, 
        help_text="A specific username for students to use for this machine."
    )
    password = models.CharField(
        max_length=100, 
        blank=True, 
        help_text="A specific password for students to use for this machine."
    )

    def clean(self):
        """Custom validation to enforce networking rules."""
        if self.is_isolated and (self.can_access_lab_resources or self.can_access_internet or self.can_access_cybercity):
            raise ValidationError(
                "If 'Is Isolated' (can access nothing) is checked, no other networking capabilities can be selected."
            )
    def save(self, *args, **kwargs):
        if not self.pk:
            return super().save(*args, **kwargs)
        before = type(self).objects.filter(pk=self.pk).values('lab_id', 'guest_os', 'username').first()
        saved_fields = kwargs.get('update_fields')
        with transaction.atomic():
            list(Lab.objects.select_for_update().filter(pk__in=sorted({before['lab_id'], self.lab_id})).order_by('pk').values_list('pk', flat=True))
            before = type(self).objects.select_for_update().filter(pk=self.pk).values('lab_id', 'guest_os', 'username').first()
            changed = before and any(before[field] != getattr(self, field) and
                (saved_fields is None or field in saved_fields) for field in ('lab_id', 'guest_os', 'username'))
            result = super().save(*args, **kwargs)
            if changed:
                from .lab_check_models import StepCheck
                StepCheck.objects.filter(lab_machine_id=self.pk).update(
                    definition_revision=models.F('definition_revision') + 1)
            return result

    class Meta:
        ordering = ['lab', 'order', 'name']
        unique_together = ('lab', 'name') # Machine names must be unique within a single lab.
        verbose_name = "Lab Machine Definition"
        verbose_name_plural = "Lab Machine Definitions"

    def __str__(self):
        return f"{self.name} for Lab: {self.lab.title}"

DEFAULT_STEP_CONTENT = """
<h3>Objective</h3>
<p>Clearly state what the student should accomplish in this step.</p>
<hr>
<h3>Procedure</h3>
<ol>
    <li>First, ...</li>
    <li>Next, ...</li>
    <li>Finally, ...</li>
</ol>
<p><em>Provide any additional notes or hints here.</em></p>
"""

class Step(models.Model):
    lab = models.ForeignKey(
        Lab,
        on_delete=models.CASCADE,
        related_name='steps',
        help_text="The lab this step belongs to."
    )
    title = models.CharField(max_length=255, blank=True, help_text="Optional title for this step.")
    content = RichTextUploadingField(help_text="Instructions for this step, with rich formatting.",default=DEFAULT_STEP_CONTENT)
    order = models.PositiveIntegerField(default=1, help_text="Order of this step within the lab.")
    estimated_time_minutes = models.PositiveIntegerField(
        blank=True, null=True,
        help_text="Estimated time in minutes to complete this step."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['lab', 'order', 'id']
        verbose_name = "Lab Step"
        verbose_name_plural = "Lab Steps"

    def __str__(self):
        step_title = self.title if self.title else f"Step {self.order}"
        return f"{step_title} (Lab: {self.lab.title})"

    
class ContentCompletion(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='content_completions'
    )
    # Generic Foreign Key fields
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Ensures a user can only complete a specific piece of content once
        unique_together = ('user', 'content_type', 'object_id')
        verbose_name = "Content Completion"
        verbose_name_plural = "Content Completions"

    def __str__(self):
        return f"{self.user.username} completed {self.content_object}"
    
class QuizAttempt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='quiz_attempts')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    score = models.FloatField()
    passed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}'s attempt on {self.quiz.title}"

class Answer(models.Model):
    quiz_attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    # Use a ForeignKey for MCQ/TF and TextField for short answers
    selected_choice = models.ForeignKey(Choice, on_delete=models.CASCADE, null=True, blank=True)
    short_answer_text = models.TextField(null=True, blank=True)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"Answer to '{self.question.text[:30]}...' in attempt {self.quiz_attempt.id}"

class LabInstance(models.Model):
    """
    Represents a live, running lab *session* for a specific user. This is the parent
    object that groups all running machine instances for a lab.
    """
    STATUS_BUILDING = 'building'
    STATUS_ACTIVE = 'active'
    STATUS_DELETING = 'deleting'
    STATUS_ERROR = 'error'
    STATUS_CHOICES = [
        (STATUS_BUILDING, 'Building'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_DELETING, 'Deleting'),
        (STATUS_ERROR, 'Error'),
    ]

    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, related_name='instances')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='lab_instances')
    
    proxmox_security_group = models.CharField(
        max_length=50, 
        null=True, 
        blank=True,
        help_text="The name of the dynamically created Proxmox security group for this lab session."
    )
    
    # Set the default status to 'building'
    status = models.CharField(
        max_length=15, 
        choices=STATUS_CHOICES, 
        default=STATUS_BUILDING,
        help_text="The current status of the lab instance."
    )

    build_log = models.TextField(
        null=True, blank=True, help_text="A real-time log of the lab creation process from the background worker."
    )
    
    build_error_message = models.TextField(
        null=True, blank=True, help_text="Stores the error message if the background build task fails."
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="For timed labs, when this instance will be automatically deleted.")

    class Meta:
        # A user can only have one active instance of a specific lab at a time.
        # This constraint should be handled in the view logic, not the DB,
        # to allow for error states.
        ordering = ['-created_at']

    def __str__(self):
        return f"Session for '{self.lab.title}' for {self.user.username}"

class LabInstanceMachine(models.Model):
    """
    Represents a single, live, cloned VM instance that is part of a user's LabInstance session.
    """
    STATUS_BUILDING = 'building'
    STATUS_RUNNING = 'running'
    STATUS_STOPPED = 'stopped'
    STATUS_ERROR = 'error'
    STATUS_CLEANUP_FAILED = 'cleanup_failed'

    lab_instance = models.ForeignKey(LabInstance, on_delete=models.CASCADE, related_name='machines')
    lab_machine_definition = models.ForeignKey(LabMachine, on_delete=models.CASCADE, related_name='instances')
    proxmox_server = models.ForeignKey(ProxmoxServer, on_delete=models.PROTECT, help_text="The Proxmox server where this instance is running.")
    
    # This is the single, correct definition for proxmox_vmid (it must be nullable)
    proxmox_vmid = models.PositiveIntegerField(
        unique=True, 
        null=True,
        blank=True,
        help_text="The unique VM/CT ID of the cloned instance on the Proxmox server."
    )
    
    proxmox_node = models.CharField(max_length=100, help_text="The Proxmox node where the instance resides.")
    name = models.CharField(max_length=255, help_text="The full name of the instance (e.g., template-name-username).")
    status = models.CharField(max_length=20, default='unknown', help_text="Last known status from Proxmox (e.g., running, stopped).")
    vnc_port = models.PositiveIntegerField(null=True, blank=True, help_text="The allocated VNC port for this machine on its host.")
    
    guacamole_connection_id = models.CharField(max_length=255, null=True, blank=True)
    guacamole_server = models.ForeignKey('GuacamoleServer', on_delete=models.PROTECT,
                                         null=True, blank=True, related_name='lab_instance_machines')
    ip_address = models.CharField(max_length=50, null=True, blank=True, editable=False)
    
    class Meta:
        ordering = ['lab_instance', 'lab_machine_definition__order']
        verbose_name = "Live Lab Machine Instance"
        verbose_name_plural = "Live Lab Machine Instances"

    def __str__(self):
        return f"VMID {self.proxmox_vmid} ({self.lab_machine_definition.name}) for {self.lab_instance.user.username}"


class LabCleanupJob(models.Model):
    """Durable work order and resource inventory, retained after session deletion."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instance = models.OneToOneField(LabInstance, null=True, blank=True, on_delete=models.SET_NULL, related_name='cleanup_job')
    instance_id_snapshot = models.PositiveIntegerField(db_index=True)
    course_id_snapshot = models.PositiveIntegerField(db_index=True)
    lab_id_snapshot = models.PositiveIntegerField()
    student_id_snapshot = models.PositiveIntegerField()
    trigger = models.CharField(max_length=32)
    status = models.CharField(max_length=16, default='queued', db_index=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    resources = models.JSONField(default=list)
    attempt_count = models.PositiveIntegerField(default=0)
    cycle_attempt_count = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    lease_token = models.UUIDField(null=True, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=120, blank=True)
    queued_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failure_notified_at = models.DateTimeField(null=True, blank=True)
    alert_lease_token = models.UUIDField(null=True, blank=True)
    alert_lease_expires_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-queued_at']


class LabCleanupAttempt(models.Model):
    job = models.ForeignKey(LabCleanupJob, on_delete=models.CASCADE, related_name='attempts')
    number = models.PositiveIntegerField()
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(default=timezone.now)
    outcome = models.CharField(max_length=16)
    summary = models.CharField(max_length=120, blank=True)
    results = models.JSONField(default=list)

    class Meta:
        ordering = ['number']
        constraints = [models.UniqueConstraint(fields=['job', 'number'], name='unique_lab_cleanup_attempt')]

class GuacamoleServer(models.Model):
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="A friendly name for this Guacamole server (e.g., 'Main Guacamole GW')."
    )
    # --- THIS FIELD REPLACES 'host' AND 'port' ---
    host_url = models.URLField(
        max_length=255,
        null=True, # Temporarily nullable for migration
        help_text="The full base URL of the Guacamole server, including the protocol (e.g., 'https://guac.example.com:8443')."
    )
    api_path = models.CharField(
        max_length=255,
        default='guacamole/api/',
        help_text="The path to the Guacamole REST API (e.g., 'guacamole/api/')."
    )
    username = models.CharField(
        max_length=100,
        help_text="Guacamole administrative user for API authentication (e.g., 'guacadmin')."
    )
    password = models.CharField(
        max_length=255,
        help_text="Password for the Guacamole administrative user. (WARNING: Store securely in production!)"
    )
    sso_secret_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="The secret key for JWT SSO authentication. Must match the 'jwt-secret' in guacamole.properties."
    )
    verify_ssl = models.BooleanField(
        default=True,
        help_text="Verify SSL certificate when connecting to Guacamole API. Set to False for self-signed certs (dev/test only)."
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Is this the default Guacamole server to use for new connections?"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.host_url})"

    def save(self, *args, **kwargs):
        if self.is_default:
            GuacamoleServer.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    def get_api_base_url(self):
        """Constructs the base URL for the Guacamole API from the host_url."""
        base_url = self.host_url.strip('/') if self.host_url else ''
        api_path = self.api_path.strip('/')
        return f"{base_url}/{api_path}/"
        
    class Meta:
        verbose_name = "Guacamole Server Connection"
        verbose_name_plural = "Guacamole Server Connections"
        ordering = ['name']
class StepQuestion(models.Model):
    """
    Represents a fill-in-the-blank question embedded within a Lab Step.
    """
    step = models.ForeignKey('Step', on_delete=models.CASCADE, related_name='questions')
    
    # Text that appears before the blank, e.g., "The command to list files is ".
    # The blank itself will be rendered in the template.
    question_text = models.CharField(max_length=500)
    
    # The text to show inside the input box before the user types.
    hint = models.CharField(max_length=100, help_text="Text to display as a placeholder in the blank (e.g., 'command...').")
    
    # The correct answer. The check will be case-insensitive.
    correct_answer = models.CharField(max_length=255, help_text="The exact correct answer for the blank.")
    
    order = models.PositiveIntegerField(default=0, help_text="Order of this question within the step (if multiple).")

    class Meta:
        ordering = ['step', 'order']
        verbose_name = "Lab Step Question"
        verbose_name_plural = "Lab Step Questions"

    def __str__(self):
        return f"Question for Step {self.step.order} in '{self.step.lab.title}'"

    def check_answer(self, submitted_answer):
        """
        Checks a user's submitted answer. Case-insensitive and strips whitespace.
        """
        return submitted_answer.strip().lower() == self.correct_answer.strip().lower()


class StepAnswer(models.Model):
    """
    Logs a student's attempt to answer a StepQuestion.
    """
    question = models.ForeignKey(StepQuestion, on_delete=models.CASCADE, related_name='answers')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='step_answers')
    
    submitted_answer = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = "Lab Step Answer"
        verbose_name_plural = "Lab Step Answers"

    def __str__(self):
        return f"Answer by {self.user.username} for Q{self.question.id} (Correct: {self.is_correct})"
    
class Profile(models.Model):
    class DisplayTheme(models.TextChoices):
        LIGHT = 'light', 'Light'
        DARK = 'dark', 'Dark'
        SYSTEM = 'system', 'Follow device'

    class ColorContrast(models.TextChoices):
        STANDARD = 'standard', 'Standard'
        HIGH = 'high', 'High contrast'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    display_theme = models.CharField(
        'Appearance', max_length=6, choices=DisplayTheme.choices, default=DisplayTheme.LIGHT,
        help_text='Choose light, dark, or follow your device setting.'
    )
    color_contrast = models.CharField(
        'Color contrast', max_length=8, choices=ColorContrast.choices, default=ColorContrast.STANDARD,
        help_text='High contrast strengthens text, links, borders, and focus indicators.'
    )
    usertag = models.CharField(
        max_length=30, 
        unique=True, 
        blank=True, 
        help_text="Your unique hacker tag or handle on the platform."
    )
    bio = models.CharField(max_length=120, blank=True, help_text="A short, one-line bio about you.")
    about_me = RichTextUploadingField(
        blank=True, 
        null=True, 
        help_text="Tell the community about yourself. What are your interests?"
    )
    profile_picture = models.ImageField(
        upload_to='profile_pictures/', 
        null=True, 
        blank=True,
        default='profile_pictures/default.png'
    )
    website_url = models.URLField(max_length=200, blank=True)
    github_url = models.URLField(max_length=200, blank=True)
    has_been_customized = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username}'s Profile"

class Grade(models.Model):
    """
    Stores a calculated grade for a user on a specific piece of course content.
    This can be populated by a quiz result, lab completion, etc.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='grades')
    course = models.ForeignKey('Course', on_delete=models.CASCADE, related_name='grades')
    
    # A generic foreign key to link to any gradeable item (Quiz, Lab, etc.)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    gradeable_item = GenericForeignKey('content_type', 'object_id')
    
    # The score, from 0 to 100.
    score = models.FloatField()
    
    # The last time this grade was updated.
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        # A user can only have one grade per gradeable item.
        unique_together = ('user', 'content_type', 'object_id')
        ordering = ['-last_updated']

    def __str__(self):
        return f"Grade for {self.user.username} on {self.gradeable_item}: {self.score}"
    
class FaqCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "FAQ Category"
        verbose_name_plural = "FAQ Categories"

    def __str__(self):
        return self.name

class Faq(models.Model):
    category = models.ForeignKey(FaqCategory, on_delete=models.CASCADE, related_name='faqs')
    question = models.CharField(max_length=255)
    answer = RichTextUploadingField()
    order = models.PositiveIntegerField(default=0)
    is_for_students = models.BooleanField(default=True, verbose_name="Visible to Students")
    is_for_instructors = models.BooleanField(default=False, verbose_name="Visible to Instructors")
    is_for_admins = models.BooleanField(default=False, verbose_name="Visible to Institution Admins")

    def clean(self):
        # Ensure at least one audience is selected.
        if not self.is_for_students and not self.is_for_instructors and not self.is_for_admins:
            raise ValidationError("An FAQ must be visible to at least one user role.")

    class Meta:
        ordering = ['category', 'order']
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"

    def __str__(self):
        return self.question


class SupportTicket(models.Model):
    # --- STATUS CHOICES ---
    STATUS_OPEN = 'open'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_CLOSED, 'Closed'),
    ]

    # --- PRIORITY CHOICES ---
    PRIORITY_LOW = 'low'
    PRIORITY_NORMAL = 'normal'
    PRIORITY_HIGH = 'high'
    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'Low'),
        (PRIORITY_NORMAL, 'Normal'),
        (PRIORITY_HIGH, 'High'),
    ]

    # --- CATEGORY CHOICES ---
    CATEGORY_GENERAL = 'general'
    CATEGORY_TECHNICAL = 'technical'
    CATEGORY_LAB = 'lab_issue'
    CATEGORY_CHOICES = [
        (CATEGORY_GENERAL, 'General Inquiry'),
        (CATEGORY_TECHNICAL, 'Technical Issue'),
        (CATEGORY_LAB, 'Lab Environment Problem'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='support_tickets')
    subject = models.CharField(max_length=255)
    
    # NEW: Use CKEditor for the description
    description = RichTextUploadingField()
    
    attachment = models.ImageField(upload_to='support_tickets/', null=True, blank=True, validators=[validate_safe_file])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    
    # NEW: Priority and Category fields
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_NORMAL)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_GENERAL)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Ticket #{self.id}: {self.subject}"


class TicketReply(models.Model):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='replies')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ticket_replies')
    message = RichTextUploadingField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Reply by {self.user.username} on Ticket #{self.ticket.id}"

class CourseAnnouncement(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='announcements')
    instructor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='course_announcements')
    title = models.CharField(max_length=255)
    body = RichTextUploadingField(help_text="The content of the announcement. This will be visible to all students in the course.")
    is_pinned = models.BooleanField(default=False, help_text="Pinned announcements will stick to the top.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', '-created_at']
        verbose_name = "Course Announcement"
        verbose_name_plural = "Course Announcements"

    def __str__(self):
        return self.title
    
    # In models.py

class CourseResource(models.Model):
    """Represents a file resource uploaded for a specific course."""

    # --- CATEGORY CHOICES ---
    CATEGORY_SYLLABUS = 'syllabus'
    CATEGORY_LESSON_PLAN = 'lesson_plan'
    CATEGORY_TEXTBOOK = 'textbook'
    CATEGORY_SLIDE_DECK = 'slide_deck'
    CATEGORY_ASSESSMENT = 'assessment'
    CATEGORY_SUPPLEMENTARY = 'supplementary'
    CATEGORY_CHOICES = [
        (CATEGORY_SYLLABUS, 'Syllabus'),
        (CATEGORY_LESSON_PLAN, 'Lesson Plans'),
        (CATEGORY_TEXTBOOK, 'Textbooks'),
        (CATEGORY_SLIDE_DECK, 'Slide Decks'),
        (CATEGORY_ASSESSMENT, 'Assessments'),
        (CATEGORY_SUPPLEMENTARY, 'Supplementary Materials'),
    ]

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='resources')
    title = models.CharField(max_length=255, help_text="A display name for the file.")
    file = models.FileField(upload_to='course_resources/%Y/%m/%d/', validators=[validate_safe_file])
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    visible_to_students = models.BooleanField(default=True, help_text="Make this resource visible to students.")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        # Ensure that at least one visibility option is selected.
        if not self.visible_to_students and not self.visible_to_instructors:
            raise ValidationError("A resource must be visible to either students or instructors (or both).")

    def __str__(self):
        return f"{self.title} for {self.course.title}"

    class Meta:
        ordering = ['category', 'title']


class NotificationLog(models.Model):
    """A read-only log of a notification sent by an instructor to students."""
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='notification_logs')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, help_text="The instructor who sent the notification.")
    recipients = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='received_notifications', help_text="Students who received this notification.")
    subject = models.CharField(max_length=255)
    body = models.TextField(help_text="The HTML body of the email that was sent.")
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        return f"'{self.subject}' sent by {self.sender.username} at {self.sent_at}"
    

    
class ShortAnswerCorrectAnswer(models.Model):
    """
    Stores a possible correct answer for a Short Answer question.
    A single question can have multiple correct answer objects.
    """
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='correct_short_answers')
    answer_text = models.CharField(max_length=255, help_text="A correct, case-insensitive answer.")

    def __str__(self):
        return self.answer_text
    
# =============================================================================
# CYBERCITY MODELS
# =============================================================================

class CyberCity(models.Model):
    """Represents a full CyberCity instance, which contains buildings and assets."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=False, help_text="Is this CyberCity publicly accessible?")
    mqtt_broker_address = models.CharField(max_length=255, blank=True)
    mqtt_broker_port = models.PositiveIntegerField(default=1883)
    mqtt_broker_username = models.CharField(max_length=255, blank=True, help_text="Optional username for the MQTT broker.")
    mqtt_broker_password = models.CharField(max_length=255, blank=True, help_text="Optional password for the MQTT broker.")

    vlan_id = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="The VLAN ID (tag) to apply to all machines in this city for network segmentation."
    )
    firewall_group = models.CharField(
        max_length=100,
        blank=True,
        help_text="The name of the Proxmox firewall security group to apply to all machines in this city."
    )

    pfsense_template = models.ForeignKey(
        'ProxmoxVMTemplate',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
        help_text="The Proxmox template to use for the city's pfSense firewall."
    )
    management_vm_template = models.ForeignKey(
        'ProxmoxVMTemplate',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
        help_text="The Proxmox template for the city's management VM."
    )
    pfsense_vmid = models.PositiveIntegerField(null=True, blank=True, unique=True)
    pfsense_vnc_port = models.PositiveIntegerField(null=True, blank=True)
    pfsense_status = models.CharField(max_length=20, default='stopped', editable=False)
    pfsense_console_port = models.PositiveIntegerField(null=True, blank=True)
    pfsense_backup_snapshot_name = models.CharField(max_length=100, null=True, blank=True, help_text="Name of the single backup snapshot.")

    # Management VM Instance State
    management_vmid = models.PositiveIntegerField(null=True, blank=True, unique=True)
    management_vnc_port = models.PositiveIntegerField(null=True, blank=True)
    management_status = models.CharField(max_length=20, default='stopped', editable=False)
    management_console_port = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "CyberCity"
        verbose_name_plural = "CyberCities"
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('cybercity_detail', args=[str(self.id)])


class CyberCityBuilding(models.Model):
    """Represents a physical building in the CyberCity simulation."""
    cybercity = models.ForeignKey(
        CyberCity,
        on_delete=models.CASCADE,
        related_name='buildings',
        help_text="The city this building belongs to."
    )
    name = models.CharField(max_length=100, help_text="The unique name of the building.")
    description = models.TextField(blank=True, help_text="A brief description of the building.")
    mqtt_base_topic = models.CharField(
        max_length=255, 
        blank=True, 
        help_text="Main topic for all attacks and ESPs in this building. e.g., 'cybercity/building1/'"
    )
    pos_x = models.IntegerField(null=True, blank=True, help_text="The X coordinate on the visualizer canvas.")
    pos_y = models.IntegerField(null=True, blank=True, help_text="The Y coordinate on the visualizer canvas.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "CyberCity Building"
        verbose_name_plural = "CyberCity Buildings"
        ordering = ['cybercity', 'name']
        unique_together = ('cybercity', 'name')

    def __str__(self):
        return f"{self.name} ({self.cybercity.name})"

    def get_absolute_url(self):
        return reverse('cybercity_building_detail', args=[str(self.cybercity.id), str(self.id)])


class CyberCityMachine(models.Model):
    """Represents a machine or system within a CyberCity building that can be powered on/off."""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    building = models.ForeignKey(
        CyberCityBuilding,
        on_delete=models.CASCADE,
        related_name='machines'
    )
    proxmox_template = models.ForeignKey(
        ProxmoxVMTemplate,
        on_delete=models.PROTECT, 
        related_name='cybercity_machines'
    )
    proxmox_vmid = models.PositiveIntegerField(null=True, blank=True, unique=True, help_text="The VMID of the live instance on Proxmox.")
    status = models.CharField(max_length=20, default='stopped', editable=False)
    active_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='active_cybercity_machine'
    )
    api_key = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, help_text="Secure API key for the machine agent.")
    vnc_port = models.PositiveIntegerField(null=True, blank=True)
    console_port = models.PositiveIntegerField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "CyberCity Machine"
        verbose_name_plural = "CyberCity Machines"
        ordering = ['building', 'name']

    def __str__(self):
        return f"{self.name} ({self.building.name})"


class CyberCityESP32(models.Model):
    """Represents an ESP32 microcontroller used for physical responses in a building."""
    name = models.CharField(max_length=100, help_text="A friendly name for the ESP32 device.")
    mac_address = models.CharField(max_length=17, unique=True, help_text="The unique MAC address of the device (e.g., 'AA:BB:CC:11:22:33').")
    building = models.ForeignKey(
        CyberCityBuilding,
        on_delete=models.CASCADE,
        related_name='esp32s'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "CyberCity ESP32"
        verbose_name_plural = "CyberCity ESP32s"
        ordering = ['building', 'name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('cybercity_esp32_detail', args=[self.building.cybercity.id, self.building.id, self.id])


class CyberCityESP32Pin(models.Model):
    """Represents a single controllable pin on an ESP32, now with stored state."""
    PIN_TYPE_LED = 'LED'
    PIN_TYPE_I2C_LED = 'I2C_LED'
    PIN_TYPE_I2C_SCREEN = 'I2C_SCREEN'
    PIN_TYPE_DUTY_CYCLE = 'DUTY_CYCLE'
    PIN_TYPE_CHOICES = [
        (PIN_TYPE_LED, 'Simple LED (On/Off)'),
        (PIN_TYPE_I2C_LED, 'I2C LED'),
        (PIN_TYPE_I2C_SCREEN, 'I2C Screen'),
        (PIN_TYPE_DUTY_CYCLE, 'Duty Cycle (e.g., Servo/Motor)'),
    ]

    esp32 = models.ForeignKey(
        CyberCityESP32,
        on_delete=models.CASCADE,
        related_name='pins'
    )
    pin_number = models.PositiveIntegerField()
    name = models.CharField(max_length=100, help_text="A functional name for the pin (e.g., 'Main Door Lock', 'Alarm Siren').")
    description = models.TextField(blank=True)
    pin_type = models.CharField(max_length=20, choices=PIN_TYPE_CHOICES, default=PIN_TYPE_LED)

    mqtt_subtopic = models.CharField(
        max_length=255,
        help_text="The sub-topic for this pin, appended to the building's base topic. (e.g., 'power/main-breaker')."
    )
    
    # Fields to store the last known state
    last_status = models.CharField(max_length=255, blank=True, null=True)
    last_status_timestamp = models.DateTimeField(blank=True, null=True)
    last_command = models.CharField(max_length=255, blank=True, null=True)
    last_command_timestamp = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "CyberCity ESP32 Pin"
        verbose_name_plural = "CyberCity ESP32 Pins"
        unique_together = ('esp32', 'pin_number') 
        ordering = ['esp32', 'pin_number']

    def get_full_topic(self):
        """Constructs the full base topic for this pin (without status/command)."""
        base = self.esp32.building.mqtt_base_topic
        if base and not base.endswith('/'):
            base += '/'
        return f"{base}{self.mqtt_subtopic}"

    def __str__(self):
        return f"Pin {self.pin_number} ({self.name}) on {self.esp32.name}"


class CyberCityAttackMonitor(models.Model):
    """Represents an attack monitoring system that sends a command to a specific pin's topic."""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    building = models.ForeignKey(
        CyberCityBuilding,
        on_delete=models.CASCADE,
        related_name='attack_monitors'
    )
    target_pin = models.ForeignKey(
        CyberCityESP32Pin,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="The specific ESP32 pin this monitor will send a command to."
    )
    attack_command = models.CharField(
        max_length=255,
        help_text="The command (payload) to send to the target pin's topic, e.g., 'ON', 'OFF', 'TOGGLE'."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "CyberCity Attack Monitor"
        verbose_name_plural = "CyberCity Attack Monitors"
        ordering = ['building', 'name']

    def __str__(self):
        return self.name

class ESP32Firmware(models.Model):
    """Represents a version of Python firmware for a specific ESP32 device."""
    esp32 = models.ForeignKey(
        CyberCityESP32,
        on_delete=models.CASCADE,
        related_name='firmwares'
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        help_text="A short description of this version (e.g., 'Initial release', 'Added LED blink')."
    )
    file = models.FileField(
        upload_to='esp32_firmware/%Y/%m/%d/',
        help_text="Upload the .py file for the ESP32."
    )
    version = models.PositiveIntegerField(
        editable=False,
        help_text="The version number, automatically incremented."
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Is this the active version to be served to the ESP32?"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-version']
        # An ESP32 can only have one firmware version with a given number
        unique_together = ('esp32', 'version')

    def __str__(self):
        return f"{self.esp32.name} - Version {self.version}"

    def save(self, *args, **kwargs):
        # Use a transaction to ensure database integrity during the update
        with transaction.atomic():
            # If this is a new firmware upload (no pk yet)
            if not self.pk:
                # Find the highest existing version number for this specific ESP32
                last_version = ESP32Firmware.objects.filter(esp32=self.esp32).aggregate(
                    max_version=Max('version')
                )['max_version'] or 0
                
                # Set the version for this new firmware
                self.version = last_version + 1

            # If this firmware is being set to active
            if self.is_active:
                # Deactivate all other firmware versions for the same ESP32
                ESP32Firmware.objects.filter(esp32=self.esp32).exclude(pk=self.pk).update(is_active=False)
            
            # Save the instance
            super().save(*args, **kwargs)

class ESP32Library(models.Model):
    """Represents a single library file associated with a firmware version."""
    firmware = models.ForeignKey(
        ESP32Firmware,
        on_delete=models.CASCADE,
        related_name='libraries'
    )
    # The path where the file should be saved on the ESP32 (e.g., 'lib/sensor.py')
    path_on_device = models.CharField(
        max_length=255,
        help_text="Full path on device, e.g., 'lib/neopixel.py' or 'utils.py'"
    )
    file = models.FileField(upload_to='esp32_libraries/%Y/%m/%d/')

    class Meta:
        verbose_name = "ESP32 Library"
        verbose_name_plural = "ESP32 Libraries"
        # A firmware version shouldn't have two libraries at the same path
        unique_together = ('firmware', 'path_on_device')

    def __str__(self):
        return f"Library for FW v{self.firmware.version}: {self.path_on_device}"
    
# In app/models.py

class MachineStateMonitor(models.Model):
    """Defines a specific state to monitor on a CyberCity machine."""
    # ... choices for monitor type and comparison ...
    MONITOR_TYPE_SERVICE = 'service'
    MONITOR_TYPE_FILE_HASH = 'file_hash'
    MONITOR_TYPE_DB_QUERY = 'db_query'
    MONITOR_TYPE_CHOICES = [
        (MONITOR_TYPE_SERVICE, 'Service Status (e.g., sshd, apache2)'),
        (MONITOR_TYPE_FILE_HASH, 'File Content Hash (SHA-256)'),
        (MONITOR_TYPE_DB_QUERY, 'Database Query Result'),
    ]
    
    COMPARISON_EQUALS = 'equals'
    COMPARISON_NOT_EQUALS = 'not_equals'
    COMPARISON_CONTAINS = 'contains'
    COMPARISON_CHOICES = [
        (COMPARISON_EQUALS, 'Equals'),
        (COMPARISON_NOT_EQUALS, 'Does Not Equal'),
        (COMPARISON_CONTAINS, 'Contains'),
    ]

    machine = models.ForeignKey(
        CyberCityMachine,
        on_delete=models.CASCADE,
        related_name='state_monitors'
    )
    name = models.CharField(max_length=100, help_text="A friendly name for this check (e.g., 'Check SSH Service').")
    monitor_type = models.CharField(max_length=20, choices=MONITOR_TYPE_CHOICES)
    
    # Path to file, service name, or the SQL query to run
    target = models.CharField(max_length=512, help_text="e.g., 'sshd', '/etc/passwd', 'SELECT status FROM services WHERE name=\"web\";'")
    
    # The condition that triggers the associated action
    comparison_type = models.CharField(max_length=20, choices=COMPARISON_CHOICES, default=COMPARISON_EQUALS)
    expected_value = models.CharField(max_length=255, help_text="e.g., 'active', 'inactive', or a specific SHA-256 hash.")
    
    # What to do when the condition is met
    trigger_on_match = models.ForeignKey(
        CyberCityAttackMonitor,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        help_text="The Attack Monitor to trigger when this condition is met."
    )
    
    # The last known state reported by the agent
    last_reported_value = models.TextField(blank=True, null=True, editable=False)
    last_reported_at = models.DateTimeField(null=True, blank=True, editable=False)
    
    is_active = models.BooleanField(default=True, help_text="Enable or disable this monitor.")

    def __str__(self):
        return f"Monitor '{self.name}' on {self.machine.name}"

class CyberCityVideoFeed(models.Model):
    """Represents a single video feed that can be displayed for a CyberCity."""
    FEED_TYPE_YOUTUBE = 'youtube'
    FEED_TYPE_HLS = 'hls'
    FEED_TYPE_DASH = 'dash'
    FEED_TYPE_CHOICES = [
        (FEED_TYPE_YOUTUBE, 'YouTube Live/Video'),
        (FEED_TYPE_HLS, 'HLS (.m3u8) Stream'),
        (FEED_TYPE_DASH, 'MPEG-DASH (.mpd) Stream'),
    ]

    city = models.ForeignKey(
        CyberCity,
        on_delete=models.CASCADE,
        related_name='video_feeds'
    )
    name = models.CharField(max_length=100, help_text="A display name for the video feed (e.g., 'Downtown Camera').")
    description = models.TextField(blank=True, help_text="An optional description of what this feed shows.")
    feed_type = models.CharField(
        max_length=10,
        choices=FEED_TYPE_CHOICES,
        default=FEED_TYPE_YOUTUBE
    )
    video_id_or_url = models.CharField(
        max_length=500,
        help_text="For YouTube, the Video ID (e.g., dQw4w9WgXcQ). For HLS/DASH, the full manifest URL."
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Uncheck to hide this feed without deleting it."
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text="Order in which to display the feeds (lower numbers first)."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "CyberCity Video Feed"
        verbose_name_plural = "CyberCity Video Feeds"
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.name} for {self.city.name}"
    
class AllocatedVNCPort(models.Model):
    """Tracks a single VNC port allocated on a specific Proxmox server."""
    port = models.IntegerField()
    proxmox_server = models.ForeignKey(ProxmoxServer, on_delete=models.CASCADE)
    # Optional: Link back to the machine for easier cleanup if needed
    # lab_instance_machine = models.OneToOneField('LabInstanceMachine', null=True, blank=True, on_delete=models.CASCADE)
    # cybercity_machine = models.OneToOneField('CyberCityMachine', null=True, blank=True, on_delete=models.CASCADE)

    class Meta:
        # This is the database-level lock that prevents race conditions
        unique_together = ('port', 'proxmox_server')
        verbose_name = "Allocated VNC Port"

    def __str__(self):
        return f"{self.proxmox_server.name}:{self.port}"

class HotspotActivity(ContentTiming):
    """A model for the hotspot labeling activity content type."""
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='hotspot_activities')
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='hotspot_activities', null=True, blank=True)
    title = models.CharField(max_length=255)
    scenario = RichTextUploadingField(help_text="The description or scenario for the activity.")
    background_image = models.ImageField(upload_to='hotspot_images/', help_text="The main image students will label.")
    order = models.PositiveIntegerField(default=0, help_text="The order of this activity within the course content.")

    class Meta:
        ordering = ['chapter__order', 'order']
        verbose_name = "Hotspot Activity"
        verbose_name_plural = "Hotspot Activities"

    def __str__(self):
        return self.title

class Label(models.Model):
    """A possible label that can be assigned to a hotspot."""
    activity = models.ForeignKey(HotspotActivity, on_delete=models.CASCADE, related_name='labels')
    text = models.CharField(max_length=100, help_text="The text for this label.")

    def __str__(self):
        return f"{self.text} (Activity: {self.activity.title})"

class Hotspot(models.Model):
    """Represents a single clickable/droppable zone on the activity image."""
    activity = models.ForeignKey(HotspotActivity, on_delete=models.CASCADE, related_name='hotspots')
    correct_label = models.ForeignKey(Label, on_delete=models.CASCADE, related_name='correct_for_hotspots')
    # Coordinates are stored as percentages to be responsive
    x_coord = models.FloatField(help_text="Left position as a percentage (0-100)")
    y_coord = models.FloatField(help_text="Top position as a percentage (0-100)")
    width = models.FloatField(help_text="Width as a percentage (0-100)")
    height = models.FloatField(help_text="Height as a percentage (0-100)")

    def __str__(self):
        return f"Hotspot for {self.correct_label.text} at ({self.x_coord}%, {self.y_coord}%)"

class HotspotAttempt(models.Model):
    """Logs a student's completion of a hotspot activity."""
    activity = models.ForeignKey(HotspotActivity, on_delete=models.CASCADE, related_name='attempts')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='hotspot_attempts')
    score = models.IntegerField(help_text="Number of correctly identified hotspots.")
    total = models.IntegerField(help_text="Total number of hotspots in the activity.")
    completed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Attempt by {self.user.username} on {self.activity.title}"

class HotspotAnswer(models.Model):
    """Logs a student's specific answer for a single hotspot."""
    attempt = models.ForeignKey(HotspotAttempt, on_delete=models.CASCADE, related_name='answers')
    hotspot = models.ForeignKey(Hotspot, on_delete=models.CASCADE)
    chosen_label = models.ForeignKey(Label, on_delete=models.CASCADE)

    @property
    def is_correct(self):
        return self.hotspot.correct_label == self.chosen_label
    
# In app/models.py

# =============================================================================
# CAPTURE THE FLAG (CTF) MODELS
# =============================================================================

class CTF(models.Model):
    """Represents a single, top-level CTF competition or event."""
    VISIBILITY_PUBLIC = 'public'
    VISIBILITY_INSTITUTION = 'institution'
    VISIBILITY_PRIVATE = 'private'
    VISIBILITY_CHOICES = [
        (VISIBILITY_PUBLIC, 'Public (Anyone can join)'),
        (VISIBILITY_INSTITUTION, 'Institutional (Users from the creator\'s institution)'),
        (VISIBILITY_PRIVATE, 'Private (Invite only, for a specific course)'),
    ]

    name = models.CharField(max_length=200, help_text="The official name of the CTF campaign.")
    description = RichTextUploadingField(help_text="A detailed description, rules, and backstory for the event.")
    start_time = models.DateTimeField(help_text="The exact date and time the competition begins.")
    end_time = models.DateTimeField(help_text="The exact date and time the competition ends and the leaderboard freezes.")
    
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default=VISIBILITY_PRIVATE)
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, help_text="If private, link to a specific course.")    
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_ctfs')
    
    # Team settings
    allow_teams = models.BooleanField(default=True, help_text="Check to allow participants to form teams.")
    max_team_size = models.PositiveIntegerField(default=4, help_text="The maximum number of members allowed on a team.")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "CTF Campaign"
        verbose_name_plural = "CTF Campaigns"
        ordering = ['-start_time']


class CTFTeam(models.Model):
    """Represents a team of participants in a specific CTF."""
    ctf = models.ForeignKey(CTF, on_delete=models.CASCADE, related_name='teams')
    name = models.CharField(max_length=100)
    leader = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='led_teams')
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='ctf_teams')

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.ctf.name})"

    class Meta:
        unique_together = ('ctf', 'name') # Team names must be unique per CTF.


class CTFCategory(models.Model):
    """A category for challenges, like 'Crypto', 'Web', 'Forensics', etc."""
    name = models.CharField(max_length=50, unique=True)
    
    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "CTF Challenge Category"
        verbose_name_plural = "CTF Challenge Categories"


class CTFChallenge(models.Model):
    """Represents a single challenge within a CTF."""
    ctf = models.ForeignKey(CTF, on_delete=models.CASCADE, related_name='challenges')
    category = models.ForeignKey(CTFCategory, on_delete=models.PROTECT, related_name='challenges')
    name = models.CharField(max_length=200)
    description = RichTextUploadingField(help_text="The challenge prompt, story, and instructions.")
    points = models.PositiveIntegerField(help_text="Points awarded for a correct submission.")
    flag = models.CharField(max_length=255, help_text="The correct flag (answer) for this challenge.")
    
    # Optional fields for different challenge types
    attached_file = models.FileField(upload_to='ctf_files/', null=True, blank=True, help_text="A file for participants to download (e.g., forensics image, pcap file).")
    external_link = models.URLField(null=True, blank=True, help_text="A link to an external challenge, like a vulnerable website.")
    linked_lab = models.ForeignKey(Lab, on_delete=models.SET_NULL, null=True, blank=True, help_text="Link to a live lab environment for this challenge.")
    
    is_visible = models.BooleanField(default=True, help_text="Uncheck to hide this challenge from participants temporarily.")

    def __str__(self):
        return f"{self.name} ({self.category.name}) - {self.points} pts"

    class Meta:
        ordering = ['category', 'points']


class CTFSubmission(models.Model):
    """Logs a correct flag submission for scoring and leaderboard purposes."""
    challenge = models.ForeignKey(CTFChallenge, on_delete=models.CASCADE, related_name='submissions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ctf_submissions')
    team = models.ForeignKey(CTFTeam, on_delete=models.CASCADE, null=True, blank=True, related_name='submissions')
    points_awarded = models.IntegerField(default=0, help_text="The actual points awarded for this submission, considering hint costs.")
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        team_name = f"Team {self.team.name}" if self.team else "Solo"
        return f"Correct submission for '{self.challenge.name}' by {self.user.username} ({team_name})"

    class Meta:
        # A user/team can only solve a challenge once.
        unique_together = ('challenge', 'user') 
        unique_together = ('challenge', 'team')
        ordering = ['submitted_at']

class CTFHint(models.Model):
    """Represents a single hint for a CTF challenge."""
    challenge = models.ForeignKey(CTFChallenge, on_delete=models.CASCADE, related_name='hints')
    text = models.TextField(help_text="The content of the hint that will be revealed to the user.")
    cost = models.PositiveIntegerField(default=0, help_text="Points deducted from the team's score when this hint is revealed (0 for a free hint).")
    order = models.PositiveIntegerField(default=1, help_text="The order the hints will be presented in (1, 2, 3...).")

    class Meta:
        ordering = ['challenge', 'order']
        verbose_name = "CTF Hint"

    def __str__(self):
        return f"Hint #{self.order} for {self.challenge.name}"

class CTFParticipant(models.Model):
    """Tracks a single user's enrollment in a single CTF."""
    ctf = models.ForeignKey(CTF, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ctf_participations')
    enrollment_time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} enrolled in {self.ctf.name}"

    class Meta:
        # A user can only enroll in a specific CTF once.
        unique_together = ('ctf', 'user')
        ordering = ['enrollment_time']

# In app/models.py

class CTFHintUnveiled(models.Model):
    """Tracks that a specific user or team has unveiled a specific hint."""
    hint = models.ForeignKey(CTFHint, on_delete=models.CASCADE, related_name='unveiled_by')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='hints_unveiled')
    team = models.ForeignKey(CTFTeam, on_delete=models.CASCADE, null=True, blank=True, related_name='hints_unveiled')
    unveiled_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        participant = self.team.name if self.team else self.user.username
        return f"Hint for '{self.hint.challenge.name}' unveiled by {participant}"

    class Meta:
        # A participant (user or team) should only be able to unveil a specific hint once.
        unique_together = (('hint', 'user'), ('hint', 'team'))

import os # Make sure os is imported
import logging # Make sure logging is imported


class DragAndDropActivity(ContentTiming):
    """A model for the drag-and-drop labeling activity content type."""
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='drag_and_drop_activities')
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='drag_and_drop_activities', null=True, blank=True)
    title = models.CharField(max_length=255)
    scenario = RichTextUploadingField(help_text="The description or scenario for the activity.")
    background_image = models.ImageField(upload_to='drag_drop_images/', help_text="The main image students will label.")
    order = models.PositiveIntegerField(default=0, help_text="The order of this activity within the course content.")

    class Meta:
        ordering = ['chapter__order', 'order']
        verbose_name = "Drag and Drop Activity"
        verbose_name_plural = "Drag and Drop Activities"

    def __str__(self):
        return self.title

class DragAndDropLabel(models.Model):
    """A possible label that can be assigned to a drop zone."""
    activity = models.ForeignKey(DragAndDropActivity, on_delete=models.CASCADE, related_name='labels')
    text = models.CharField(max_length=100, help_text="The text for this label.")

    def __str__(self):
        return f"{self.text} (Activity: {self.activity.title})"

class DropZone(models.Model):
    """Represents a single droppable zone on the activity image."""
    activity = models.ForeignKey(DragAndDropActivity, on_delete=models.CASCADE, related_name='drop_zones')
    correct_label = models.ForeignKey(DragAndDropLabel, on_delete=models.CASCADE, related_name='correct_for_zones')
    # Coordinates are stored as percentages to be responsive
    x_coord = models.FloatField(help_text="Left position as a percentage (0-100)")
    y_coord = models.FloatField(help_text="Top position as a percentage (0-100)")
    width = models.FloatField(help_text="Width as a percentage (0-100)")
    height = models.FloatField(help_text="Height as a percentage (0-100)")

    def __str__(self):
        return f"Drop Zone for {self.correct_label.text} at ({self.x_coord}%, {self.y_coord}%)"

class DragAndDropAttempt(models.Model):
    """Logs a student's completion of a drag-and-drop activity."""
    activity = models.ForeignKey(DragAndDropActivity, on_delete=models.CASCADE, related_name='attempts')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='drag_and_drop_attempts')
    score = models.IntegerField(help_text="Number of correctly placed labels.")
    total = models.IntegerField(help_text="Total number of drop zones in the activity.")
    completed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Attempt by {self.user.username} on {self.activity.title}"

class DragAndDropAnswer(models.Model):
    """Logs a student's specific answer for a single drop zone."""
    attempt = models.ForeignKey(DragAndDropAttempt, on_delete=models.CASCADE, related_name='answers')
    drop_zone = models.ForeignKey(DropZone, on_delete=models.CASCADE)
    chosen_label = models.ForeignKey(DragAndDropLabel, on_delete=models.CASCADE)

    @property
    def is_correct(self):
        return self.drop_zone.correct_label == self.chosen_label
    
class CodingActivity(ContentTiming):
    """A model for an interactive coding exercise."""
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='coding_activities')
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='coding_activities', null=True, blank=True)
    title = models.CharField(max_length=255)
    description = RichTextUploadingField(help_text="The problem description, requirements, and examples for the student.")
    
    LANGUAGE_PYTHON = 'python'
    LANGUAGE_BASH = 'bash'
    LANGUAGE_POWERSHELL = 'powershell'
    LANGUAGE_CHOICES = [
        (LANGUAGE_PYTHON, 'Python'),
        (LANGUAGE_BASH, 'Bash'),
        (LANGUAGE_POWERSHELL, 'PowerShell'),
    ]
    language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, default=LANGUAGE_PYTHON)
    
    starter_code = models.TextField(blank=True, help_text="Boilerplate code to start the student off.")
    order = models.PositiveIntegerField(default=0, help_text="The order of this activity within the course content.")

    class Meta:
        ordering = ['chapter__order', 'order']
        verbose_name = "Coding Activity"
        verbose_name_plural = "Coding Activities"

    def __str__(self):
        return self.title

class TestCase(models.Model):
    """A single test case to validate a student's code submission."""
    activity = models.ForeignKey(CodingActivity, on_delete=models.CASCADE, related_name='test_cases')
    name = models.CharField(max_length=255, help_text="A descriptive name for the test case (e.g., 'Test with positive numbers').")
    setup_code = models.TextField(blank=True, help_text="Optional: Code to run before the student's code (e.g., defining variables).")
    test_code = models.TextField(blank=True, help_text="The code that runs *after* the student's code to check its output or state.")
    expected_output = models.TextField(blank=True, help_text="The exact expected output from stdout for this test case to pass.")
    is_hidden = models.BooleanField(default=False, help_text="If checked, the student will not see the details of this test, only whether it passed or failed.")

    def __str__(self):
        return f"Test '{self.name}' for {self.activity.title}"

class CodingSubmission(models.Model):
    """Logs a student's attempt at a coding activity."""
    activity = models.ForeignKey(CodingActivity, on_delete=models.CASCADE, related_name='submissions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='coding_submissions')
    submitted_code = models.TextField()
    passed_all_tests = models.BooleanField(default=False)
    results = models.JSONField(help_text="Stores detailed results for each test case.")
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        status = "Passed" if self.passed_all_tests else "Failed"
        return f"Submission by {self.user.username} for {self.activity.title} ({status})"
    
class ForumThread(models.Model):
    """Represents a single discussion thread within a course forum."""
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='forum_threads')
    title = models.CharField(max_length=255)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='forum_threads')
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_pinned = models.BooleanField(default=False, help_text="Pinned threads stick to the top of the list.")
    is_locked = models.BooleanField(default=False, help_text="Locked threads do not allow new replies.")

    class Meta:
        ordering = ['-is_pinned', '-last_activity']
        verbose_name = "Forum Thread"
        verbose_name_plural = "Forum Threads"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('forum_thread', args=[self.course.id, self.id])

class ForumPost(models.Model):
    """Represents a single post or reply within a forum thread."""
    thread = models.ForeignKey(ForumThread, on_delete=models.CASCADE, related_name='posts')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='forum_posts')
    content = RichTextUploadingField(help_text="Write your reply here.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = "Forum Post"
        verbose_name_plural = "Forum Posts"

    def __str__(self):
        return f"Post by {self.author.username} in '{self.thread.title}'"

class Conversation(models.Model):
    """Represents a private conversation thread, typically between a student and instructor(s)."""
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='conversations', help_text="The course this conversation is about.")
    subject = models.CharField(max_length=255)
    # --- UPDATED: Use a 'through' model to handle archived status ---
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        related_name='conversations',
        through='ConversationParticipant' # This is the important part
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"'{self.subject}' in {self.course.title}"

class ConversationParticipant(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    is_archived = models.BooleanField(default=False)

    class Meta:
        unique_together = ('conversation', 'user')

class Message(models.Model):
    """A single message within a conversation."""
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    content = RichTextUploadingField()
    sent_at = models.DateTimeField(auto_now_add=True)
    
    # We use a ManyToManyField to track who has read the message
    read_by = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='read_messages', blank=True)

    class Meta:
        ordering = ['sent_at']

    def __str__(self):
        return f"Message by {self.author.username} at {self.sent_at.strftime('%Y-%m-%d %H:%M')}"

# This signal updates the conversation's timestamp whenever a new message is saved
@receiver(post_save, sender=Message)
def update_conversation_timestamp(sender, instance, created, **kwargs):
    if created:
        instance.conversation.save() # This triggers the auto_now=True on Conversation.updated_at

@receiver(post_save, sender=Message)
def update_conversation_on_new_message(sender, instance, created, **kwargs):
    if created:
        conversation = instance.conversation
        # 1. Update the conversation's last activity timestamp
        conversation.save() 
        
        # 2. Un-archive the conversation for all participants except the author
        ConversationParticipant.objects.filter(
            conversation=conversation
        ).exclude(
            user=instance.author
        ).update(is_archived=False)

class CertificateTemplate(models.Model):
    """Stores a template for certificates, including the background image and text placement."""
    name = models.CharField(max_length=255, help_text="An internal name for this template.")
    course = models.OneToOneField(Course, on_delete=models.SET_NULL, null=True, blank=True, help_text="Assign this template to a specific course. Leave blank for a generic template.")
    background_image = models.ImageField(upload_to='certificate_templates/', help_text="The background image for the certificate (e.g., with borders, logos). Recommended size: 1200x900px.")
    student_name_y_coord = models.PositiveIntegerField(default=400, help_text="Vertical position (pixels from top) for the student's name.")
    course_name_y_coord = models.PositiveIntegerField(default=500, help_text="Vertical position (pixels from top) for the course title.")
    completion_date_y_coord = models.PositiveIntegerField(default=600, help_text="Vertical position (pixels from top) for the completion date.")
    font_color = models.CharField(max_length=7, default='#000000', help_text="Hex color code for the text (e.g., #000000 for black).")

    def __str__(self):
        return self.name

class Certificate(models.Model):
    """Represents a certificate awarded to a user for completing a course."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='certificates')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='certificates')
    template = models.ForeignKey(CertificateTemplate, on_delete=models.PROTECT, related_name='certificates')
    issued_at = models.DateTimeField(auto_now_add=True)
    unique_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    def __str__(self):
        return f"Certificate for {self.user.username} in {self.course.title}"

class Badge(models.Model):
    """Represents a digital badge that can be awarded to users."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(help_text="What does this badge represent?")
    icon = models.ImageField(upload_to='badge_icons/', help_text="Upload a small, preferably square, icon for the badge.")
    required_courses = models.ManyToManyField(Course, blank=True, related_name='badges')
    required_labs = models.ManyToManyField(Lab, blank=True, related_name='badges')
    required_quizzes = models.ManyToManyField(Quiz, blank=True, related_name='badges')
    
    def __str__(self):
        return self.name

class UserBadge(models.Model):
    """Links a user to a badge they have earned."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='badges')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name='user_badges')
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'badge')

    def __str__(self):
        return f"{self.user.username} earned '{self.badge.name}'"
    
class ProxmoxVMLock(models.Model):
    """A simple model to create a database row that can be locked to prevent race conditions."""
    lock_name = models.CharField(max_length=100, unique=True, primary_key=True)
    is_locked = models.BooleanField(default=False)
    last_allocated_vmid = models.IntegerField(default=100)

    def __str__(self):
        return f"Lock: {self.lock_name}"
    
class OpenWebUIAssistant(models.Model):
    """
    Stores connection details and configuration for an OpenWebUI/Ollama server instance.
    """
    name = models.CharField(max_length=100, unique=True, help_text="A unique name for this AI assistant instance (e.g., 'General Student Assistant', 'Institution X Assistant').")
    PROVIDER_OPENWEBUI = 'openwebui'
    PROVIDER_OPENAI = 'openai'
    PROVIDER_CHOICES = [(PROVIDER_OPENWEBUI, 'OpenWebUI'), (PROVIDER_OPENAI, 'OpenAI API')]
    BEHAVIOR_CHOICES = [
        ('guided', 'Guided questions'), ('balanced', 'Balanced coaching'),
        ('direct', 'Direct explanations'),
    ]
    provider = models.CharField(max_length=10, choices=PROVIDER_CHOICES, default=PROVIDER_OPENWEBUI)
    host = models.URLField(max_length=255, blank=True, help_text="OpenWebUI URL. Leave blank for the direct OpenAI API.")
    api_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="The API key for authenticating with the OpenWebUI server, if required."
    )
    model_name = models.CharField(
        max_length=100,
        default='llama3:latest',
        help_text="The name of the Ollama model to use for this assistant (e.g., 'llama3:latest', 'mistral:latest')."
     )
    verify_ssl = models.BooleanField(
        default=True,
        help_text="Uncheck only if the AI server uses a self-signed SSL certificate."
    )
    tutor_behavior = models.CharField(max_length=10, choices=BEHAVIOR_CHOICES, default='balanced')
    tutor_instructions = models.TextField(
        blank=True, help_text='Staff instructions for how the AI tutor teaches. Student messages cannot change these instructions.'
    )
    tutor_grounding_enabled = models.BooleanField(
        default=False, help_text='Let the tutor search accessible material in a course selected by the student.'
    )
    is_active = models.BooleanField(default=True, help_text="Enable or disable this assistant across the platform.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

class ScenarioActivity(ContentTiming):
    """
    Represents the main container for a scenario-based troubleshooting activity.
    """
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='scenario_activities')
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='scenario_activities', null=True, blank=True)
    title = models.CharField(max_length=255)
    scenario_description = RichTextUploadingField(help_text="The initial scenario brief for the student.")
    order = models.PositiveIntegerField(default=0, help_text="The order of this activity within the course content.")

    class Meta:
        ordering = ['chapter__order', 'order']
        verbose_name = "Scenario Activity"
        verbose_name_plural = "Scenario Activities"

    def __str__(self):
        return self.title

class ScenarioPersona(models.Model):
    """
    Defines the AI's persona, background information, and the goal for a specific scenario.
    """
    activity = models.OneToOneField(ScenarioActivity, on_delete=models.CASCADE, related_name='persona')
    persona_name = models.CharField(max_length=100, help_text="The name of the customer the AI will role-play as (e.g., 'John Doe').")
    issue_summary = models.CharField(max_length=255, help_text="A one-sentence summary of the customer's problem (e.g., 'Cannot connect to the office Wi-Fi').")
    background_details = models.TextField(help_text="All the hidden information and context for the AI. The AI will only reveal these details when the student asks relevant questions. Be specific.")
    resolution_criteria = models.TextField(help_text="Describe the condition(s) under which the issue is considered resolved. The AI will use this to know when to provide the completion code.")
    completion_code = models.CharField(max_length=50, help_text="The secret code the AI will give the student once the issue is resolved.")

    def __str__(self):
        return f"Persona for '{self.activity.title}'"

class ScenarioAttempt(models.Model):
    """
    Stores the conversation history for a single student's attempt at a scenario.
    """
    activity = models.ForeignKey(ScenarioActivity, on_delete=models.CASCADE, related_name='attempts')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='scenario_attempts')
    conversation_history = models.JSONField(default=list)
    is_complete = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('activity', 'user') # Allow only one attempt per user for now

class AIGeneratedCourse(models.Model):
    """Tracks the entire AI course generation process from prompt to completion."""
    STATUS_CHOICES = [
        ('PENDING_BLUEPRINT', 'Pending Blueprint Generation'),
        ('PENDING_REVIEW', 'Pending Instructor Review'),
        ('GENERATING_CONTENT', 'Generating Content'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]

    # The instructor who initiated the request
    instructor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    # The final course that is created (can be null until the process is complete)
    course = models.OneToOneField(Course, on_delete=models.SET_NULL, null=True, blank=True, related_name='ai_generation_job')

    # The initial prompt from the instructor
    initial_prompt = models.TextField()

    # The raw JSON blueprint returned by the AI
    ai_blueprint = models.JSONField(null=True, blank=True)
    
    # The blueprint after the instructor has reviewed and possibly edited it
    reviewed_blueprint = models.JSONField(null=True, blank=True)

    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='PENDING_BLUEPRINT')
    
    # For tracking errors
    error_message = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"AI Course Job for '{self.initial_prompt[:50]}...' by {self.instructor.username}"

class FlashcardDeck(ContentTiming):
    """A deck of flashcards, serving as a new content type within a course."""
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='flashcard_decks')
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='flashcard_decks', null=True, blank=True)
    title = models.CharField(max_length=255)
    description = RichTextUploadingField(help_text="A description of what this flashcard deck covers.")
    order = models.PositiveIntegerField(default=0, help_text="The order of this activity within the course content.")

    class Meta:
        ordering = ['chapter__order', 'order']
        verbose_name = "Flashcard Deck"
        verbose_name_plural = "Flashcard Decks"

    def __str__(self):
        return self.title

class Flashcard(models.Model):
    """A single flashcard with a term and a definition."""
    deck = models.ForeignKey(FlashcardDeck, on_delete=models.CASCADE, related_name='flashcards')
    term = models.TextField(help_text="The front of the card (the term or question).")
    definition = RichTextUploadingField(help_text="The back of the card (the definition or answer).")
    
    # Add null=True and blank=True to this line
    image = models.ImageField(upload_to='flashcard_images/', null=True, blank=True, help_text="Optional: An image to display with the term.")
    
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        verbose_name = "Flashcard"
        verbose_name_plural = "Flashcards"

    def __str__(self):
        return self.term[:60]

class FlashcardDeckAttempt(models.Model):
    """Tracks a user's study session with a flashcard deck."""
    deck = models.ForeignKey(FlashcardDeck, on_delete=models.CASCADE, related_name='attempts')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='flashcard_attempts')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_studied_card = models.ForeignKey(Flashcard, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Attempt by {self.user.username} on {self.deck.title}"
    
class UserFlashcardMastery(models.Model):
    """Tracks a user's mastery level for a single flashcard."""
    LEVEL_NEW = 'new'
    LEVEL_LEARNING = 'learning'
    LEVEL_MASTERED = 'mastered'
    MASTERY_LEVEL_CHOICES = [
        (LEVEL_NEW, 'New'),
        (LEVEL_LEARNING, 'Learning'),
        (LEVEL_MASTERED, 'Mastered'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='flashcard_mastery')
    flashcard = models.ForeignKey(Flashcard, on_delete=models.CASCADE, related_name='mastered_by')
    mastery_level = models.CharField(max_length=10, choices=MASTERY_LEVEL_CHOICES, default=LEVEL_NEW)
    last_reviewed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'flashcard')
        ordering = ['last_reviewed_at']

    def __str__(self):
        return f"{self.user.username}'s mastery of '{self.flashcard.term[:30]}...' is {self.get_mastery_level_display()}"
    
class CourseBackup(models.Model):
    """Stores a complete, serialized snapshot of a course at a specific point in time."""
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='backups')
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    description = models.CharField(max_length=255, blank=True, help_text="A brief note about this version (e.g., 'Pre-semester final').")
    backup_data = models.JSONField(help_text="The serialized JSON data of the entire course content.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Course Backup"
        verbose_name_plural = "Course Backups"

    def __str__(self):
        return f"Backup of '{self.course.title}' from {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
class TeamScenario(ContentTiming):
    """The main container for a Red Team vs. Blue Team exercise."""
    # --- THIS ENTIRE BLOCK NEEDS TO BE UPDATED ---
    STATUS_PENDING = 'pending'
    STATUS_STARTING = 'starting'
    STATUS_ACTIVE = 'active'
    STATUS_STOPPING = 'stopping'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending (Setup not started)'),
        (STATUS_STARTING, 'Starting...'),
        (STATUS_ACTIVE, 'Active (Environment is running)'),
        (STATUS_STOPPING, 'Stopping...'),
        (STATUS_COMPLETED, 'Completed (Exercise has ended)'),
        (STATUS_FAILED, 'Failed'),
    ]

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='team_scenarios')
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='team_scenarios', null=True, blank=True)
    title = models.CharField(max_length=255)
    description = RichTextUploadingField(help_text="A detailed description of the scenario, rules of engagement, and backstory.")
    duration_minutes = models.PositiveIntegerField(help_text="The total duration of the match in minutes.")
    max_team_size = models.PositiveIntegerField(default=4, help_text="The maximum number of members allowed on a team.")
    order = models.PositiveIntegerField(default=0)
    
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_PENDING, editable=False)
    last_error_message = models.TextField(null=True, blank=True, editable=False, help_text="Stores the last error message if the scenario fails to start or stop.")
    
    class Meta:
        ordering = ['chapter__order', 'order']
        verbose_name = "Team Scenario"
        verbose_name_plural = "Team Scenarios"

    def update_scores(self):
        """
        Calculates and updates scores for the Blue Team based on service uptime.
        Red Team scores are handled transactionally upon flag capture.
        """
        if self.status != self.STATUS_ACTIVE:
            return

        blue_team = self.teams.filter(team_type=ScenarioTeam.TEAM_BLUE).first()

        # Calculate and award Blue Team score from service uptime
        if blue_team:
            uptime_points_this_minute = 0
            # Get all 'up' services for machines assigned to the Blue Team
            up_services = ScenarioService.objects.filter(
                machine__scenario=self,
                machine__assigned_to=ScenarioMachine.ASSIGN_BLUE,
                status=ScenarioService.STATUS_UP
            )
            for service in up_services:
                uptime_points_this_minute += service.points_per_minute
            
            if uptime_points_this_minute > 0:
                blue_team.score = F('score') + uptime_points_this_minute
                blue_team.save()
                self.logs.create(
                    message=f"Awarded {uptime_points_this_minute} points for service uptime.",
                    team_type=ScenarioLog.TEAM_BLUE,
                    points=uptime_points_this_minute
                )

    def __str__(self):
        return self.title
    
class ScenarioTeam(models.Model):
    """Represents a single team (Red or Blue) within a scenario."""
    TEAM_BLUE = 'blue'
    TEAM_RED = 'red'
    TEAM_TYPE_CHOICES = [
        (TEAM_BLUE, 'Blue Team (Defenders)'),
        (TEAM_RED, 'Red Team (Attackers)'),
    ]

    scenario = models.ForeignKey(TeamScenario, on_delete=models.CASCADE, related_name='teams')
    team_type = models.CharField(max_length=10, choices=TEAM_TYPE_CHOICES)
    name = models.CharField(max_length=100)
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='scenario_teams', blank=True)
    
    # This will store the live score during an active instance of the scenario
    current_points = models.IntegerField(default=0, editable=False)

    class Meta:
        unique_together = ('scenario', 'name')
        ordering = ['team_type']

    def __str__(self):
        return f"{self.name} ({self.get_team_type_display()})"

class ScenarioMachine(models.Model):
    """Defines a single VM template to be deployed in the scenario."""
    ASSIGN_BLUE = 'blue'
    ASSIGN_RED = 'red'
    ASSIGN_NEUTRAL = 'neutral'
    ASSIGN_CHOICES = [
        (ASSIGN_BLUE, 'Blue Team'),
        (ASSIGN_RED, 'Red Team'),
        (ASSIGN_NEUTRAL, 'Neutral / Environment'),
    ]
    
    scenario = models.ForeignKey(TeamScenario, on_delete=models.CASCADE, related_name='machine_definitions')
    name = models.CharField(max_length=100, help_text="A descriptive name, e.g., 'Web Server', 'Firewall', 'Kali Attacker'.")
    proxmox_vm_template = models.ForeignKey(ProxmoxVMTemplate, on_delete=models.PROTECT)
    assigned_to = models.CharField(max_length=10, choices=ASSIGN_CHOICES, help_text="Which team gets console access to this machine.")
    
    # Store live instance data here
    proxmox_vmid = models.PositiveIntegerField(null=True, blank=True, editable=False)
    ip_address = models.CharField(max_length=50, null=True, blank=True, editable=False)

    def __str__(self):
        return f"{self.name} for {self.scenario.title}"

class ScenarioService(models.Model):
    """A critical service on a machine to be monitored for uptime."""
    machine = models.ForeignKey(ScenarioMachine, on_delete=models.CASCADE, related_name='services')
    name = models.CharField(max_length=100, help_text="e.g., 'Apache Web Server', 'MySQL Database'")
    port = models.PositiveIntegerField()
    points_per_check = models.PositiveIntegerField(default=10, help_text="Points awarded to the Blue Team for each successful uptime check.")
    is_active = models.BooleanField(default=True, editable=False) # To track live status

    def __str__(self):
        return f"Service '{self.name}' on port {self.port}"

class ScenarioObjective(models.Model):
    """A goal for a team (usually Red Team) to achieve for points."""
    scenario = models.ForeignKey(TeamScenario, on_delete=models.CASCADE, related_name='objectives')
    name = models.CharField(max_length=255)
    description = models.TextField()
    flag = models.CharField(max_length=255, help_text="The flag to be submitted to capture this objective.")
    points_awarded = models.PositiveIntegerField(help_text="Points awarded to the capturing team.")
    
    # To track live status
    is_completed = models.BooleanField(default=False, editable=False)
    completed_by_team = models.ForeignKey(ScenarioTeam, on_delete=models.SET_NULL, null=True, blank=True, editable=False)
    
    def __str__(self):
        return self.name

class ScenarioLog(models.Model):
    """Stores a running log of events for an active scenario."""
    TEAM_BLUE = 'blue'
    TEAM_RED = 'red'
    TEAM_SYSTEM = 'system'
    TEAM_TYPE_CHOICES = [
        (TEAM_BLUE, 'Blue Team'),
        (TEAM_RED, 'Red Team'),
        (TEAM_SYSTEM, 'System'),
    ]

    scenario = models.ForeignKey(TeamScenario, on_delete=models.CASCADE, related_name='logs')
    timestamp = models.DateTimeField(auto_now_add=True)
    team_type = models.CharField(max_length=10, choices=TEAM_TYPE_CHOICES, default=TEAM_SYSTEM)
    message = models.TextField()
    points = models.IntegerField(default=0, help_text="Points awarded or deducted in this event.")

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp.strftime('%H:%M:%S')}] {self.message}"
    
class StudentVMIDPool(models.Model):
    """Assigns a specific range of VMIDs on a Proxmox server to a student."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='vmid_pools',
        limit_choices_to={'is_superuser': False, 'is_staff': False},
        help_text="The student who owns this pool."
    )
    proxmox_server = models.ForeignKey(
        ProxmoxServer,
        on_delete=models.CASCADE,
        related_name='student_pools'
    )
    vmid_start = models.PositiveIntegerField()
    vmid_end = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'proxmox_server')
        verbose_name = "Student VMID Pool"
        verbose_name_plural = "Student VMID Pools"

    def __str__(self):
        return f"Pool for {self.user.username} on {self.proxmox_server.name} ({self.vmid_start}-{self.vmid_end})"

class AllocatedVMID(models.Model):
    """Tracks a single VMID that is currently in use from a student's pool."""
    pool = models.ForeignKey(StudentVMIDPool, on_delete=models.CASCADE, related_name='allocated_vmids')
    vmid = models.PositiveIntegerField(unique=True)
    lab_machine = models.OneToOneField(
        LabInstanceMachine,
        on_delete=models.CASCADE,
        related_name='allocated_vmid'
    )

    def __str__(self):
        return f"VMID {self.vmid} allocated to {self.pool.user.username}"
    
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def assign_vmid_pool_on_user_creation(sender, instance, created, **kwargs):
    """
    This signal handler runs automatically after a User object is saved.
    If a new, non-staff user is created, it assigns them a VMID pool.
    """
    # Only run for new users who are not staff/admins
    if created:
        # Get all Proxmox servers that have a defined VMID range
        servers = ProxmoxServer.objects.filter(
            vmid_range_start__isnull=False,
            vmid_range_end__isnull=False
        )

        for server in servers:
            # Find the last VMID that was assigned on this server
            last_assigned_vmid = StudentVMIDPool.objects.filter(
                proxmox_server=server
            ).aggregate(max_end=Max('vmid_end'))['max_end']

            # Determine the starting point for the new pool
            if last_assigned_vmid:
                next_start = last_assigned_vmid + 1
            else:
                next_start = server.vmid_range_start

            pool_size = 10
            new_pool_end = next_start + (pool_size - 1)

            # Check if the new pool fits within the server's total available range
            if new_pool_end <= server.vmid_range_end:
                StudentVMIDPool.objects.create(
                    user=instance,
                    proxmox_server=server,
                    vmid_start=next_start,
                    vmid_end=new_pool_end
                )
                print(f"Assigned VMID pool {next_start}-{new_pool_end} on {server.name} to {instance.username}")
            else:
                # Log an error if there's no more space
                print(f"ERROR: Not enough VMIDs left on server {server.name} to create a new pool for {instance.username}.")

class License(models.Model):
    """A singleton model to store the application's license information."""
    # The encrypted JWT received from the license server
    license_key = models.TextField(
        blank=True, 
        help_text="The encrypted license key from the licensing server."
    )
    # The unique ID for this specific server hardware
    machine_fingerprint = models.CharField(
        max_length=255, 
        blank=True, 
        editable=False, 
        help_text="The unique hardware ID of this server."
    )
    # The rolling 30-day expiration date
    expires_at = models.DateTimeField(
        null=True, 
        blank=True
    )
    # The last time the app successfully contacted the license server
    last_checked_at = models.DateTimeField(
        null=True, 
        blank=True
    )
    # The final, hard expiration date for the contract
    contract_end_date = models.DateField(
        null=True, 
        blank=True
    )
    # The maximum number of users allowed by the license
    max_users = models.PositiveIntegerField(
        default=0
    )
    # The feature flag for the CyberCity module
    cybercity_enabled = models.BooleanField(
        default=False
    )
    plugin_revoked_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        if self.expires_at:
            return f"License expires on {self.expires_at.strftime('%Y-%m-%d')}"
        return "No License Found"

    def save(self, *args, **kwargs):
        # This ensures that only one License object can ever exist
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Prevent deletion of the singleton object
        pass

def student_submission_upload_path(instance, filename):
    """Generates a unique path: submissions/course_X/activity_Y/username_timestamp.ext"""
    ext = filename.split('.')[-1]
    timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
    safe_filename = f"{instance.user.username}_{timestamp}.{ext}"
    return f"submissions/course_{instance.activity.course.id}/activity_{instance.activity.id}/{safe_filename}"

class FileSubmissionActivity(ContentTiming):
    """The assignment instructions created by the instructor."""
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='file_submissions')
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='file_submissions', null=True, blank=True)
    title = models.CharField(max_length=255)
    instructions = RichTextUploadingField(help_text="Detailed instructions for the assignment.")
    max_score = models.PositiveIntegerField(default=100, help_text="Maximum possible points for this assignment.")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['chapter__order', 'order']
        verbose_name = "File Submission Activity"
        verbose_name_plural = "File Submission Activities"

    def __str__(self):
        return self.title

class FileSubmission(models.Model):
    """The actual file submitted by the student and the instructor's grade/feedback."""
    activity = models.ForeignKey(FileSubmissionActivity, on_delete=models.CASCADE, related_name='submissions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='file_submissions')
    file = models.FileField(upload_to=student_submission_upload_path, validators=[validate_safe_file])
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    # Grading fields
    is_graded = models.BooleanField(default=False)
    score = models.FloatField(null=True, blank=True)
    instructor_feedback = models.TextField(blank=True, null=True, help_text="Feedback provided by the instructor.")
    graded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='graded_submissions')
    graded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-submitted_at']
        unique_together = ('activity', 'user') # Ensure only one active submission per student (they can overwrite it)

    def __str__(self):
        return f"Submission by {self.user.username} for {self.activity.title}"

# Keep models registered under the app label while isolating the lab check schema.
from .lab_check_models import StepCheck, ValidationLease, ValidationRun, ValidationResult  # noqa: E402,F401
from .pbq_models import PBQActivity, PBQArtifact, PBQQuestion, PBQAnswerField, PBQChoice, PBQAcceptedAnswer, PBQAttempt, PBQResponse, PBQGradeEvent  # noqa: E402,F401
from .gradebook_models import CourseGradingPolicy, CourseCategoryWeight, GradebookItemPolicy  # noqa: E402,F401
from .plugin_models import InstalledConnector, ConnectorConfiguration, PluginInstallJob, PluginAuditEvent  # noqa: E402,F401
