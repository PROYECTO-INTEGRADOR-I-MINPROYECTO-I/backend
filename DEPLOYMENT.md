# Despliegue — Backend

API en Django 6.1 + Django REST Framework. Se despliega en Render como web service, con tres ambientes independientes.

El backend es **API-only** en los ambientes desplegados: no sirve archivos estáticos y el panel de admin solo se registra cuando `DEBUG` está activo, es decir únicamente en local.

---

## 1. Setup local

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # y editar los valores
python manage.py migrate
python manage.py runserver
```

Comprobar que responde:

```bash
curl http://localhost:8000/api/test/
# {"message": "Server is working!"}
```

El admin queda en http://localhost:8000/admin/ (solo local). Para entrar, crear un usuario con `python manage.py createsuperuser`.

Si no existe `.env`, el proyecto arranca igual usando SQLite, para que un clon recién bajado no quede bloqueado.

---

## 2. Variables de entorno

| Variable | ¿Secreta? | Descripción |
|---|---|---|
| `ENVIRONMENT` | No | `dev`, `qa` o `prod`. Determina los defaults de las demás y activa HSTS en prod. |
| `DEBUG` | No | `True` solo en local. **Siempre `False` en qa y prod.** |
| `SECRET_KEY` | **Sí** | En `dev` hay un default inseguro. En qa/prod es obligatoria: si falta, la app no levanta a propósito. |
| `ALLOWED_HOSTS` | No | Dominios que Django acepta, separados por coma. Render inyecta además `RENDER_EXTERNAL_HOSTNAME`, que se añade solo. |
| `DATABASE_URL` | **Sí** | Cadena de conexión a Supabase. Si no está, cae a SQLite. |
| `CORS_ALLOWED_ORIGINS` | No | Orígenes del frontend autorizados a llamar la API, con esquema y separados por coma. |
| `CSRF_TRUSTED_ORIGINS` | No | Mismos dominios que el anterior. |
| `EMAIL_HOST` y compañía | **Sí** (la password) | Opcionales. Ver la sección de correo más abajo. |

Valores por ambiente:

| Variable | dev (local) | dev (Render) | qa | prod |
|---|---|---|---|---|
| `ENVIRONMENT` | `dev` | `dev` | `qa` | `prod` |
| `DEBUG` | `True` | `False` | `False` | `False` |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | `planificapp-api-dev.onrender.com` | `planificapp-api-qa.onrender.com` | `planificapp-api-prod.onrender.com` |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | `https://planificapp-web-dev.onrender.com` | `https://planificapp-web-qa.onrender.com` | `https://planificapp-web-prod.onrender.com` |
| `CSRF_TRUSTED_ORIGINS` | igual que CORS | igual que CORS | igual que CORS | igual que CORS |
| `DATABASE_URL` | sin definir → SQLite | sin definir → SQLite | sin definir → SQLite | **obligatoria** (Supabase) |

### Cookies entre dominios

El frontend y la API viven en dominios distintos, así que en los ambientes desplegados las cookies se emiten con `SameSite=None` y `Secure=True`. Con el valor por defecto de Django (`Lax`) el navegador no adjuntaría la cookie de sesión en las peticiones `fetch` del frontend y la autenticación no funcionaría, aunque CORS estuviera bien configurado.

`SameSite=None` exige `Secure`, por eso ambos ajustes viven en el mismo bloque `if not DEBUG`. En local no aplica: ahí el proxy de Vite hace que todo sea mismo origen.

`CORS_ALLOW_ALL_ORIGINS` no se usa en ningún ambiente, ni siquiera en local. Cada ambiente declara explícitamente el dominio de **su** frontend. Como `CORS_ALLOW_CREDENTIALS` está en `True` (necesario para autenticación por cookie), el comodín `*` sería además inválido según la especificación de CORS.

---

## 3. Base de datos (Supabase)

**Estado actual:** solo **prod** apunta a Supabase. dev y qa usan SQLite local mientras se trabaja en las máquinas del equipo.

| Ambiente | Base de datos |
|---|---|
| dev | SQLite local (`db.sqlite3`) |
| qa | SQLite local |
| prod | Supabase Postgres, proyecto `tymsvhihcwwzjkrfkyol`, región `us-east-1` |

Si en algún momento se despliegan los servicios dev o qa en Render sin `DATABASE_URL`, funcionarán con SQLite sobre disco efímero: **la base se borra en cada deploy**. Sirve para probar que la API responde, no para guardar datos. Para darles persistencia, basta cargarles su propia `DATABASE_URL` en Render.

### Obtener la cadena de conexión

1. Entrar al proyecto en Supabase.
2. Botón **Connect** (arriba) → pestaña **Session pooler**.
3. Copiar la cadena y reemplazar `[YOUR-PASSWORD]` por la contraseña de la base.

Queda así:

```
postgresql://postgres.<project-ref>:<password>@aws-1-<region>.pooler.supabase.com:5432/postgres
```

Para prod queda:

```
postgresql://postgres.tymsvhihcwwzjkrfkyol:<password>@aws-1-us-east-1.pooler.supabase.com:5432/postgres
```

**Usar el Session pooler (puerto 5432), no el Transaction pooler (6543).** Django mantiene conexiones persistentes vía `conn_max_age=600`, y el transaction pooler recicla la conexión entre transacciones: produce errores intermitentes de *prepared statement already exists*, del tipo que solo aparece bajo carga.

Por si acaso, `settings.py` detecta el puerto: si la URL apunta al 6543, desactiva automáticamente `conn_max_age` y los prepared statements. Funciona, pero se pierde el beneficio de las conexiones persistentes, así que el 5432 sigue siendo lo correcto.

Si el plan de Supabase no permite tres proyectos, la alternativa es un proyecto con un schema por ambiente, añadiendo a la URL:

```
?options=-csearch_path%3D<schema>
```

En ese caso, producción debería tener siempre su propio proyecto aparte.

---

## 3.b Correo

En `dev` los correos se imprimen en la consola y no hay nada que configurar.

En qa y prod, si no se define `EMAIL_HOST` se usa un backend *dummy* que descarta los mensajes silenciosamente. Esto no impide que la aplicación arranque, pero `manage.py check --deploy` lo reporta como error pendiente, que es justamente la señal de que falta configurarlo.

Cuando haga falta enviar correo de verdad, cargar en Render:

```
EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, EMAIL_USE_TLS, DEFAULT_FROM_EMAIL
```

`EMAIL_HOST_PASSWORD` es un secreto: va solo en el dashboard, nunca en el repositorio.

---

## 4. Primer despliegue en Render

El repositorio incluye `render.yaml` con los tres servicios ya definidos.

1. En Render: **New → Blueprint** y conectar este repositorio.
2. Render lee `render.yaml` y propone `planificapp-api-dev`, `planificapp-api-qa` y `planificapp-api-prod`, cada uno atado a su rama.
3. Las variables marcadas `sync: false` (`DATABASE_URL`) **no viajan en el repositorio**: hay que cargarlas a mano en cada servicio, en *Environment*.
4. `SECRET_KEY` usa `generateValue: true`, así que Render genera una distinta por servicio. No hay que hacer nada.
5. Primer deploy: Render ejecuta `./build.sh` (instala dependencias y corre migraciones) y luego arranca con gunicorn.

El health check apunta a `/api/health/`.

---

## 5. Ambientes y flujo de promoción

| Ambiente | Rama | Servicio |
|---|---|---|
| dev | `develop` | `planificapp-api-dev` |
| qa | `qa` | `planificapp-api-qa` |
| prod | `main` | `planificapp-api-prod` |

Cada merge a una de esas ramas dispara automáticamente el deploy del servicio correspondiente. El flujo es `develop` → `qa` → `main`: nada llega a producción sin haber pasado por qa.

---

## 5.b Health check

`GET /api/health/` es el endpoint que Render consulta para decidir si un deploy quedó sano y para vigilar el servicio después.

No se limita a devolver 200: ejecuta un `SELECT 1` contra la base de datos, porque una aplicación viva que no alcanza su base no puede atender nada útil.

```bash
curl https://planificapp-api-prod.onrender.com/api/health/
```

```json
{ "status": "ok", "environment": "prod", "database": "ok" }
```

Si la base no responde, devuelve **503** con `"status": "unhealthy"`, que es lo que Render interpreta como servicio caído. El detalle del error solo se incluye cuando `DEBUG` está activo: en qa y prod expondría el host y el usuario de la base en un endpoint público.

Esta ruta está exenta del redirect a HTTPS (`SECURE_REDIRECT_EXEMPT` en `settings.py`). Sin esa excepción, un health check que llegue sin la cabecera `X-Forwarded-Proto` recibiría un 301 y Render daría el deploy por fallido aunque el servicio estuviera perfecto.

`GET /api/test/` se mantiene aparte como prueba rápida de que la API responde; no consulta la base.

---

## 6. Verificación después de desplegar

Preflight de CORS, que es la prueba real sin depender del navegador:

```bash
curl -i -X OPTIONS https://planificapp-api-qa.onrender.com/api/test/ \
  -H "Origin: https://planificapp-web-qa.onrender.com" \
  -H "Access-Control-Request-Method: GET"
```

Debe devolver `200` con `Access-Control-Allow-Origin` igual al `Origin` enviado y `Access-Control-Allow-Credentials: true`.

Repetir con un origen que no esté en la lista: la cabecera `Access-Control-Allow-Origin` **no** debe aparecer. Si aparece, la configuración está abierta de más.

Además, por ambiente:

- `GET /api/test/` responde el JSON esperado.
- Una URL inexistente devuelve un 404 plano, no el traceback de Django (confirma `DEBUG=False`).
- `/admin/` responde 404 (confirma que el panel no está expuesto).

---

## 7. Problemas frecuentes

**`DisallowedHost at /`** — el dominio no está en `ALLOWED_HOSTS`. Añadirlo en las variables del servicio en Render.

**Error de CORS en la consola del navegador** — el origen exacto del frontend no está en `CORS_ALLOWED_ORIGINS`. Debe incluir el esquema (`https://`) y no llevar barra final.

**La primera petición tarda ~50 segundos** — en el plan free de Render el web service se suspende tras 15 minutos sin tráfico y arranca en frío. Afecta solo al backend; los static sites del frontend se sirven por CDN y no se suspenden.

**Fallan las migraciones en el build** — normalmente es la `DATABASE_URL`. Revisar que se usó el puerto 5432, que la contraseña está bien y que los caracteres especiales de la contraseña van codificados para URL (`@` → `%40`, `#` → `%23`, etc.).

**`ImproperlyConfigured: Set the SECRET_KEY environment variable`** — es el comportamiento buscado: en qa y prod la clave es obligatoria. Cargarla en Render.
