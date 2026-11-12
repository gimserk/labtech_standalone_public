"""Restore the missing merge node for concurrent Cyber City and lab clone migrations.

0029 and later migrations reference this historical merge; it has no schema
operations. Keep both branches in the migration graph.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0027_assignment_rubrics"),
        ("app", "0021_lab_clone_type"),
    ]

    operations = []
