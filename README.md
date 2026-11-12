# Sistema de gestión escolar

Aplicación web para administrar expedientes escolares. Está construida con
Flask, MySQL y Waitress, y puede usarse desde otras computadoras de la misma
red local.

## Requisitos

- Windows
- Python y las dependencias de `requirements.txt`
- XAMPP (servicio MySQL)

## Instalación rápida

1. Instala Python y XAMPP en la computadora que alojará el sistema.
2. Abre una terminal en esta carpeta e instala las dependencias:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Inicia MySQL desde el panel de XAMPP. Crea la base de datos e importa
   `escuela_db.sql`.
4. Copia `config.example.json` como `instance\config.json` y completa la
   configuración de MySQL. Genera una clave secreta con:

   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

   Usa el resultado como `secret_key`. No compartas ni subas
   `instance\config.json`: contiene credenciales y una clave privada.
5. Inicia la aplicación:

   ```powershell
   python proyecto.py
   ```

La guía con los pasos detallados para instalar, migrar datos y configurar el
acceso en Windows está en [INSTALACION_ANFITRION_WINDOWS.md](INSTALACION_ANFITRION_WINDOWS.md).

## Acceso

- En la computadora anfitriona: <http://127.0.0.1:5000>
- En otra computadora de la misma red: `http://IP-LOCAL-DEL-ANFITRION:5000`

Para conocer la IP que deben usar los demás equipos, ejecuta `ipconfig` en la
computadora anfitriona y busca la dirección IPv4 de su conexión activa. La
ventana de la terminal debe permanecer abierta mientras se usa la aplicación;
pulsa `Ctrl+C` en ella para detener el servidor.

## Nota de seguridad

Waitress sirve la aplicación por HTTP, sin cifrar el tráfico. Úsala solo en
una red local privada y confiable; no expongas el puerto 5000 a Internet.
