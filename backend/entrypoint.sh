#!/bin/bash
set -e

echo "Waiting for PostgreSQL..."
while ! pg_isready -h postgres -p 5432 -U procurelens; do
    sleep 1
done
echo "PostgreSQL is ready!"

echo "Running migrations..."
python manage.py migrate --noinput

echo "Creating superuser if not exists..."
python manage.py shell -c "
from authentication.models import User
if not User.objects.filter(email='admin@procurelens.com').exists():
    User.objects.create_superuser(
        username='admin',
        email='admin@procurelens.com',
        password='admin123',
        first_name='Admin',
        last_name='ProcureLens',
        is_verified=True
    )
    print('Superuser created: admin@procurelens.com / admin123')
else:
    print('Superuser already exists')
" || true

echo "Starting server..."
exec "$@"
