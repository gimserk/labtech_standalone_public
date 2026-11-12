from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("app", "0067_cybercity_soc_managed_appliances")]

    operations = [
        migrations.AddField(
            model_name="cybercityesp32pin",
            name="led_count",
            field=models.PositiveSmallIntegerField(
                default=1, help_text="WS2811 strip: number of LEDs (1–300). Ignored for other pin types."
            ),
        ),
        migrations.AddField(
            model_name="cybercityesp32pin",
            name="led_brightness",
            field=models.PositiveSmallIntegerField(
                default=64, help_text="WS2811 strip: maximum channel brightness (1–255; default 64)."
            ),
        ),
        migrations.AlterField(
            model_name="cybercityesp32pin",
            name="pin_type",
            field=models.CharField(
                max_length=20,
                default="LED",
                choices=[
                    ("LED", "Simple LED (On/Off)"),
                    ("I2C_LED", "I2C LED"),
                    ("I2C_SCREEN", "I2C Screen"),
                    ("DUTY_CYCLE", "Duty Cycle (e.g., Servo/Motor)"),
                    ("WS2811", "WS2811 addressable RGB LED strip"),
                ],
            ),
        ),
    ]
