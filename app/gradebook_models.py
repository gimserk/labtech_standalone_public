"""Course grading configuration, kept separate from student attempts."""
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models.signals import post_delete


CATEGORIES = (
    'textpage', 'video', 'audio', 'quiz', 'lab', 'hotspotactivity',
    'draganddropactivity', 'codingactivity', 'scenarioactivity',
    'flashcarddeck', 'filesubmissionactivity', 'pbqactivity',
)
DEFAULT_GRADED = frozenset(CATEGORIES) - frozenset(('textpage', 'video', 'audio', 'flashcarddeck'))


def activity_models():
    from . import models as app_models
    names = (
        'TextPage', 'Video', 'Audio', 'Quiz', 'Lab', 'HotspotActivity',
        'DragAndDropActivity', 'CodingActivity', 'ScenarioActivity',
        'FlashcardDeck', 'FileSubmissionActivity', 'PBQActivity',
    )
    return dict(zip(CATEGORIES, (getattr(app_models, name) for name in names)))


def default_item_policy(item):
    key = item._meta.model_name
    if key not in CATEGORIES:
        raise ValidationError('Unsupported course activity.')
    if key not in DEFAULT_GRADED:
        return False, Decimal('0.00')
    if key == 'quiz':
        total = sum((q.points for q in item.questions.all()), 0)
        return True, Decimal(total if total > 0 else 100)
    if key in ('filesubmissionactivity', 'pbqactivity'):
        return True, Decimal(item.max_score if item.max_score > 0 else 100)
    return True, Decimal('100.00')


def validated_decimal(value, label, *, maximum=None):
    try:
        amount = Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise ValidationError(f'{label} must be a number.') from exc
    if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -2 or (maximum is not None and amount > maximum):
        raise ValidationError(f'{label} must be nonnegative, finite and have at most two decimal places.')
    return amount


class CourseGradingPolicy(models.Model):
    course = models.OneToOneField('Course', on_delete=models.CASCADE, related_name='grading_policy')
    mode = models.CharField(max_length=8, choices=(('points', 'Points'), ('weighted', 'Weighted')), default='points')

    @classmethod
    def for_course(cls, course):
        return cls.objects.filter(course=course).first() or cls(course=course, mode='points')


class CourseCategoryWeight(models.Model):
    course = models.ForeignKey('Course', on_delete=models.CASCADE, related_name='gradebook_weights')
    category_key = models.CharField(max_length=32, choices=[(k, k) for k in CATEGORIES])
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=('course', 'category_key'), name='course_gradebook_category_unique')]

    def clean(self):
        super().clean()
        if self.category_key not in CATEGORIES:
            raise ValidationError('Unsupported category.')
        validated_decimal(self.weight, 'Weight', maximum=Decimal('100'))


class GradebookItemPolicy(models.Model):
    course = models.ForeignKey('Course', on_delete=models.CASCADE, related_name='gradebook_items')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    included_in_grade = models.BooleanField(default=False)
    points_possible = models.DecimalField(max_digits=9, decimal_places=2, default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=('course', 'content_type', 'object_id'), name='course_gradebook_item_unique')]

    def clean(self):
        super().clean()
        model = self.content_type.model_class() if self.content_type_id else None
        if model not in activity_models().values():
            raise ValidationError('Unsupported gradebook item.')
        if not model.objects.filter(pk=self.object_id, course_id=self.course_id).exists():
            raise ValidationError('Gradebook item does not belong to this course.')
        points = validated_decimal(self.points_possible, 'Points')
        if points > Decimal('9999999.99') or (self.included_in_grade and points <= 0):
            raise ValidationError('Included items must have a positive, supported point value.')


@transaction.atomic
def save_grading_policy(course, mode, weights, items):
    """Validate a full course policy and persist it without changing attempts."""
    from .models import Course
    Course.objects.select_for_update().get(pk=course.pk)
    if mode not in ('points', 'weighted'):
        raise ValidationError('Invalid grading mode.')
    if set(weights) - set(CATEGORIES):
        raise ValidationError('Unsupported category weight.')

    normalized_weights = {key: validated_decimal(weights.get(key, 0), 'Weight', maximum=Decimal('100')) for key in CATEGORIES}
    types = {key: ContentType.objects.get_for_model(model) for key, model in activity_models().items()}
    effective = {}
    for key, model in activity_models().items():
        for item in model.objects.filter(course=course):
            default = default_item_policy(item)
            saved = GradebookItemPolicy.objects.filter(course=course, content_type=types[key], object_id=item.pk).first()
            if mode == 'weighted' and saved is None and not normalized_weights[key]:
                default = (False, default[1])
            effective[(key, item.pk)] = (saved.included_in_grade, saved.points_possible) if saved else default

    for (key, item_id), value in items.items():
        if key not in types or (key, item_id) not in effective:
            raise ValidationError('Item does not belong to this course.')
        included, points = value
        if not isinstance(included, bool):
            raise ValidationError('Item inclusion must be a boolean.')
        amount = validated_decimal(points, 'Points')
        if amount > Decimal('9999999.99') or (included and amount <= 0):
            raise ValidationError('Included items must have positive points.')
        effective[(key, item_id)] = (included, amount)

    if mode == 'weighted':
        active = {key for (key, _), (included, points) in effective.items() if included and points > 0}
        if sum((normalized_weights[key] for key in active), Decimal('0')) != Decimal('100'):
            raise ValidationError('Active category weights must total exactly 100%.')
        if any(normalized_weights[key] for key in set(CATEGORIES) - active):
            raise ValidationError('Categories without included items must have zero weight.')

    CourseGradingPolicy.objects.update_or_create(course=course, defaults={'mode': mode})
    for key in CATEGORIES:
        CourseCategoryWeight.objects.update_or_create(course=course, category_key=key, defaults={'weight': normalized_weights[key]})
    for (key, item_id), value in items.items():
        included, points = effective[(key, item_id)]
        record = GradebookItemPolicy.objects.filter(course=course, content_type=types[key], object_id=item_id).first()
        if record is None:
            record = GradebookItemPolicy(course=course, content_type=types[key], object_id=item_id)
        record.included_in_grade, record.points_possible = included, points
        record.full_clean()
        GradebookItemPolicy.objects.update_or_create(
            course=course, content_type=types[key], object_id=item_id,
            defaults={'included_in_grade': included, 'points_possible': points},
        )


def remove_item_policy(sender, instance, **kwargs):
    GradebookItemPolicy.objects.filter(
        course_id=instance.course_id,
        content_type=ContentType.objects.get_for_model(sender), object_id=instance.pk,
    ).delete()


for _key, _model in activity_models().items():
    post_delete.connect(remove_item_policy, sender=_model, weak=False, dispatch_uid=f'gradebook_{_key}_delete')


def serialize_grading_policy(course):
    policy = CourseGradingPolicy.for_course(course)
    return {
        'mode': policy.mode,
        'weights': {key: str(value) for key, value in
                    CourseCategoryWeight.objects.filter(course=course).values_list('category_key', 'weight')},
        'items': [
            {'type': entry.content_type.model, 'source_id': entry.object_id,
             'included': entry.included_in_grade, 'points': str(entry.points_possible)}
            for entry in GradebookItemPolicy.objects.filter(course=course).select_related('content_type')
        ],
    }


def restore_grading_policy(target, payload, item_map):
    """Translate every explicit item policy to the new course's item IDs."""
    if payload is None:
        return
    values = {}
    for record in payload.get('items', []):
        key = record['type']
        original = record['source_id']
        if key not in CATEGORIES or (key, original) not in item_map:
            raise ValidationError('Grading policy refers to missing course content.')
        new_item = item_map[(key, original)]
        if new_item.course_id != target.pk or new_item._meta.model_name != key:
            raise ValidationError('Grading policy refers to another course.')
        values[(key, new_item.pk)] = (record['included'], record['points'])
    save_grading_policy(target, payload['mode'], payload.get('weights', {}), values)


def copy_course_grading_policy(source, target, item_map):
    restore_grading_policy(target, serialize_grading_policy(source), item_map)
