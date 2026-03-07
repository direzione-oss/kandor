from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0024_add_messaggio_chat'),
    ]

    operations = [
        migrations.AlterField(
            model_name='messaggiochat',
            name='testo',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='messaggiochat',
            name='foto_url',
            field=models.URLField(blank=True, default='', verbose_name='URL Foto'),
        ),
    ]
