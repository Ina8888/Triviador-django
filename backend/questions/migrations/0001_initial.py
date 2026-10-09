
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
            ],
            options={
                'verbose_name': 'Category',
                'verbose_name_plural': 'Categories',
            },
        ),
        migrations.CreateModel(
            name='ChoiceQuestion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField()),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='%(class)ss', to='questions.category')),
            ],
            options={
                'verbose_name': 'Choice Question',
                'verbose_name_plural': 'Choice Questions',
            },
        ),
        migrations.CreateModel(
            name='AnswerOption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.CharField(max_length=255)),
                ('is_correct', models.BooleanField(default=False)),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='options', to='questions.choicequestion')),
            ],
            options={
                'verbose_name': 'Answer Option',
                'verbose_name_plural': 'Answer Options',
            },
        ),
        migrations.CreateModel(
            name='NumericQuestion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField()),
                ('correct_answer', models.IntegerField()),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='%(class)ss', to='questions.category')),
            ],
            options={
                'verbose_name': 'Numeric Question',
                'verbose_name_plural': 'Numeric Questions',
            },
        ),
    ]
