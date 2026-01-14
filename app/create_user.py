from django.contrib.auth import get_user_model
User = get_user_model()
user, created = User.objects.get_or_create(email='test@eventyay.com', defaults={'is_superuser': True, 'is_staff': True})
user.set_password('TestPassword123!')
user.save()
print('✅ User created successfully!' if created else '✅ Password updated successfully!')
print(f'Email: test@eventyay.com')
print(f'Password: TestPassword123!')
