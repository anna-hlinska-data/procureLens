#!/bin/bash
set -e

echo "Waiting for PostgreSQL..."
while ! pg_isready -h postgres -p 5432 -U "${POSTGRES_USER:-procurelens}"; do
    sleep 1
done
echo "PostgreSQL is ready!"

echo "Running migrations..."
python manage.py migrate --noinput

if [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    echo "Creating superuser if not exists..."
    python manage.py shell -c "
import os
from authentication.models import User
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@procurelens.com')
if not User.objects.filter(email=email).exists():
    User.objects.create_superuser(
        username='admin',
        email=email,
        password=os.environ['DJANGO_SUPERUSER_PASSWORD'],
        first_name='Admin',
        last_name='ProcureLens',
        is_verified=True
    )
    print(f'Superuser created: {email}')
else:
    print('Superuser already exists')
" || true
else
    echo "DJANGO_SUPERUSER_PASSWORD not set, skipping superuser creation"
fi

echo "Starting server..."
exec "$@"
