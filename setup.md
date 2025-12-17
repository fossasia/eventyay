docker compose up -d --build

<!-- create super user -->
docker exec -ti eventyay-next-web python manage.py createsuperuser


Web interface: http://localhost:8000
Admin panel: http://localhost:8000/admin


<!-- stop the application -->
docker compose down