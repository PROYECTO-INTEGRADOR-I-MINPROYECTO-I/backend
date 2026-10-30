# PlanificApp — Backend

API REST de PlanificApp: Django 6.1, Django REST Framework y autenticación con JWT. En producción usa Postgres (Supabase) y está desplegada en Render.

## URLs públicas

| Qué | URL |
|---|---|
| Aplicación (frontend) | https://planificapp-web-prod.onrender.com/ |
| API | https://planificapp-api-prod.onrender.com/api/ |
| Health check | https://planificapp-api-prod.onrender.com/api/health/ |
| Documentación (Swagger) | https://planificapp-api-prod.onrender.com/api/docs/ |

El plan gratuito de Render apaga el servicio cuando no tiene uso, así que la primera petición puede tardar unos 50 segundos en responder.

## Cuenta demo

| Email | Contraseña |
|---|---|
| `demo@planificapp.com` | `demo1234` |

Los pasos de prueba sugeridos están en el [README del frontend](https://github.com/PROYECTO-INTEGRADOR-I-MINPROYECTO-I/frontend#probar-en-producción). Para crear la cuenta con eventos y gestiones de ejemplo se usa `python manage.py seed_demo`. En prod el comando necesita `--force`.

## Arranque local

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # opcional: sin .env usa SQLite
python manage.py migrate
python manage.py seed_demo       # cuenta demo con datos
python manage.py runserver       # http://localhost:8000/api/
```

Tests: `pytest`.

## Variables de entorno

| Variable | Descripción |
|---|---|
| `ENVIRONMENT` | `dev`, `qa` o `prod` |
| `DEBUG` | `True` solo en local |
| `SECRET_KEY` | Clave de Django. Obligatoria en qa y prod |
| `JWT_SIGNING_KEY` | Firma de los JWT. Obligatoria en qa y prod |
| `DATABASE_URL` | Cadena de Postgres (session pooler de Supabase, puerto 5432). Sin ella se usa SQLite |
| `ALLOWED_HOSTS` | Dominios aceptados, separados por coma |
| `CORS_ALLOWED_ORIGINS` / `CSRF_TRUSTED_ORIGINS` | URL del frontend de cada ambiente |

Los ambientes, Supabase, el correo y la promoción `develop` → `qa` → `main` se explican en [DEPLOYMENT.md](./DEPLOYMENT.md).
