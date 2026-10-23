from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('app', '0025_tekcon_nfc_target_ctf')]
    operations = [migrations.AddField(model_name='tekconnfcconfiguration', name='target_course', field=models.ForeignKey(to='app.course', null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, help_text='Optional workshop course for badge check-in; used only when no CTF target is selected.'))]
