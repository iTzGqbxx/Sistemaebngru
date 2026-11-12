# Instalar y ejecutar en Windows

## Instalación inicial

1. Instala Python y XAMPP en la computadora anfitriona.
2. Copia la carpeta del proyecto a una ubicación fija.
3. Abre PowerShell en `SISTEMA PRODUCTO FUNCIONAL` e instala las dependencias:

   ```powershell
   python -m pip install -r requirements.txt
   ```

4. Inicia MySQL desde XAMPP. Apache solo hace falta para phpMyAdmin; no se usa
   para servir la aplicación.
5. En phpMyAdmin, crea la base `escuela_ebngru` e importa `escuela_db.sql`.
   Crea el usuario `gabounermb@localhost` con permisos limitados solo a esa
   base de datos.
6. Crea `instance\config.json` copiando `config.example.json`. Completa la
   contraseña de MySQL y genera una clave secreta nueva:

   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

   Pega el resultado en `secret_key`. No subas `instance/config.json` a GitHub.
7. Para trasladar los expedientes existentes, exporta la base actual completa
   e impórtala en el anfitrión; copia también `instance\uploads` por un medio
   privado. `escuela_db.sql` contiene el esquema y usuarios iniciales, pero no
   los registros actuales de estudiantes ni sus adjuntos.

## Iniciar el sistema

1. Inicia MySQL desde XAMPP.
2. Abre una terminal en la carpeta `SISTEMA PRODUCTO FUNCIONAL`.
3. Ejecuta:

   ```powershell
   python proyecto.py
   ```

4. Deja la ventana abierta mientras se usa el sistema. En el anfitrión abre
   `http://127.0.0.1:5000`. Desde otra computadora de la misma red, abre
   `http://IP-LOCAL-DEL-ANFITRION:5000` (por ejemplo,
   `http://192.168.1.107:5000`).
5. Para apagar el servidor, vuelve a la terminal y pulsa `Ctrl+C`.

Si las otras computadoras no pueden conectarse, permite el puerto TCP 5000
entrante solo desde la subred local en el Firewall de Windows y comprueba que
no estén conectadas a una red Wi-Fi de invitados con aislamiento.

## Límite importante de seguridad

Waitress es un servidor WSGI de producción, pero este modo usa HTTP sin TLS:
los datos enviados entre computadoras de la red no están cifrados. Úsalo solo
en una red local privada y confiable; no abras el puerto 5000 en el router ni
lo expongas a Internet. Para proteger el tráfico de datos escolares también
frente a otros usuarios de la red, hará falta HTTPS en el futuro.
