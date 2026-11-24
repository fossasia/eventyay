from django.db import migrations, models


# The default name given to the team created together with an organizer, in English and in every
# translation shipped when this migration was written. Existing teams with one of these names are the
# Core Organizing Team of their organizer.
CORE_TEAM_NAMES = (
    'Alap szervezőcsapat',
    'Ana Organizasyon Ekibi',
    'Core Organizing Team',
    'Echipa principală de organizare',
    'Equip organitzador principal',
    'Equipa Nuclear de Organização',
    'Equipe principal de organização',
    'Equipo organizador principal',
    'Galvenā organizatoru komanda',
    'Główny zespół organizacyjny',
    'Hlavní organizační tým',
    'Kern-Organisationsteam',
    'Kerneteam for organisering',
    'Kernorganisatieteam',
    'Kjerneteam for organisering',
    'Kärnteam för organisering',
    'Nhóm tổ chức chính',
    'Osrednja organizacijska ekipa',
    'Pasukan Penganjur Teras',
    'Team organizzativo principale',
    'Tim Inti Penyelenggara',
    'Timu Kuu ya Uratibu',
    'Ydinjärjestäjätiimi',
    'Équipe organisatrice principale',
    'Κεντρική Ομάδα Διοργάνωσης',
    'Основен организационен екип',
    'Основна команда організаторів',
    'Основная команда организаторов',
    'تیم اصلی برگزارکننده',
    'فريق التنظيم الأساسي',
    'مرکزی تنظیمی ٹیم',
    'मुख्य आयोजन टीम',
    'मुख्य आयोजन संघ',
    'মূল আয়োজক দল',
    'મુખ્ય આયોજન ટીમ',
    'மைய ஒழுங்கமைப்பு குழு',
    'కోర్ ఆర్గనైజింగ్ టీమ్',
    'കോർ ഓർഗനൈസിംഗ് ടീം',
    'මූලික සංවිධාන කණ්ඩායම',
    'ทีมผู้จัดหลัก',
    'ក្រុមរៀបចំស្នូល',
    'コア運営チーム',
    '核心主辦團隊',
    '核心组织团队',
    '핵심 운영팀',
)


def flag_core_teams(apps, schema_editor):
    Team = apps.get_model('base', 'Team')
    Team.objects.filter(name__in=CORE_TEAM_NAMES).update(is_core_team=True)


class Migration(migrations.Migration):
    dependencies = [
        ('base', '0093_team_can_view_event_info'),
    ]

    operations = [
        migrations.AddField(
            model_name='team',
            name='is_core_team',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Members of the core team are the owners of the organizer account and can perform '
                    'owner-only actions such as anonymizing event data. Only platform administrators can '
                    'change this.'
                ),
                verbose_name='Core Organizing Team',
            ),
        ),
        migrations.RunPython(flag_core_teams, migrations.RunPython.noop),
    ]
