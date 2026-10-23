from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('app', '0024_tekcon_nfc_auth')]
    operations = [migrations.AddField(model_name='tekconnfcconfiguration', name='target_ctf', field=models.ForeignKey(to='app.ctf',null=True,blank=True,on_delete=django.db.models.deletion.SET_NULL,help_text='Optional CTF to enroll badge attendees in.'))]
