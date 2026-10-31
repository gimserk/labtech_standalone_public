from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("app", "0055_cybercity_soc_simulations")]
    operations = [migrations.AddField(
        model_name="cybercitysocsimulation", name="sequence",
        field=models.PositiveIntegerField(default=0, help_text="Instructor-defined reveal order."),
    )]
