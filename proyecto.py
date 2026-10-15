import sys
from pathlib import Path
from uuid import uuid4

import mysql.connector
from mysql.connector import Error
from flask import Flask, abort, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

app = Flask(__name__)
app.secret_key = 'EBNGRU_secret_key_super_secure'
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024
UPLOAD_FOLDER = Path(app.instance_path) / 'uploads'

ARCHIVOS_INSCRIPCION = {
    'doc_partida_nacimiento': ('Partida de nacimiento del estudiante', {'.pdf', '.jpg', '.jpeg', '.png', '.webp'}),
    'doc_cedula_estudiante': ('Copia de cédula del estudiante', {'.pdf', '.jpg', '.jpeg', '.png', '.webp'}),
    'doc_carton_vacunas': ('Copia de cartón de vacunas', {'.pdf', '.jpg', '.jpeg', '.png', '.webp'}),
    'doc_cedula_representante': ('Copia de cédula del representante', {'.pdf', '.jpg', '.jpeg', '.png', '.webp'}),
    'doc_rif_representante': ('Copia del RIF actualizado', {'.pdf', '.jpg', '.jpeg', '.png', '.webp'}),
    'foto_estudiante': ('Foto tipo carnet del estudiante', {'.jpg', '.jpeg', '.png', '.webp'}),
    'foto_representante': ('Foto tipo carnet del representante', {'.jpg', '.jpeg', '.png', '.webp'}),
}


def asegurar_tabla_archivos(cursor):
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS archivos_inscripcion (
            id INT NOT NULL AUTO_INCREMENT,
            inscripcion_id INT NOT NULL,
            tipo VARCHAR(100) NOT NULL,
            nombre_archivo VARCHAR(255) NOT NULL,
            nombre_original VARCHAR(255) NOT NULL,
            extension VARCHAR(10) NOT NULL,
            creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            INDEX idx_archivos_inscripcion (inscripcion_id),
            CONSTRAINT fk_archivos_inscripcion
                FOREIGN KEY (inscripcion_id) REFERENCES inscripciones(id)
                ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci
    ''')


@app.errorhandler(RequestEntityTooLarge)
def archivo_demasiado_grande(error):
    if request.endpoint == 'inscripcion' and 'usuario' in session:
        flash('Los archivos adjuntos superan el límite total de 32 MB.', 'error')
        return redirect(url_for('inscripcion'))
    return error


class DatabaseConnection:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseConnection, cls).__new__(cls)
            cls._instance.connection = None
        return cls._instance

    def _create_connection(self):
        databases_to_try = ["escuela_ebngru", "escuela_db"]
        last_error = None
        for db_name in databases_to_try:
            try:
                cnx = mysql.connector.connect(
                    user="root",
                    password="",
                    host="localhost",
                    database=db_name,
                    port="3306"
                )
                return cnx
            except Error as e:
                last_error = e
                if getattr(e, 'errno', None) == 1049:
                    continue
                break
        raise last_error

    def get_connection(self):
        try:
            if self.connection is None or not self.connection.is_connected():
                self.connection = self._create_connection()
            return self.connection
        except Exception:
            self.connection = self._create_connection()
            return self.connection

    def close_connection(self):
        if hasattr(self, 'connection') and self.connection and self.connection.is_connected():
            self.connection.close()
            self.connection = None

db_connection = DatabaseConnection()

@app.route('/')
def index():
    if 'usuario' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        password = request.form['password']
        
        conn = db_connection.get_connection()
        c = conn.cursor(dictionary=True)
        c.execute('SELECT * FROM usuarios WHERE usuario = %s AND password = %s', (usuario, password))
        usuario_db = c.fetchone()
        conn.close()
        
        if usuario_db:
            session['usuario'] = usuario_db['usuario']
            session['rol'] = usuario_db['rol']
            return redirect(url_for('dashboard'))
        else:
            flash('Usuario o contraseña incorrectos.', 'error')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('usuario', None)
    session.pop('rol', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/editar_inscripcion/<int:id>', methods=['GET', 'POST'])
def editar_inscripcion(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    rol = session.get('rol')
    if rol == 'administracion':
        flash('Acceso denegado: El personal de administración solo tiene permisos para registrar estudiantes, no para modificarlos.', 'error')
        return redirect(url_for('ver_datos'))
        
    conn = db_connection.get_connection()
    c = conn.cursor(dictionary=True)
    c.execute('SELECT * FROM inscripciones WHERE id = %s', (id,))
    ins = c.fetchone()
    conn.close()
    
    if not ins:
        flash('Inscripción no encontrada.', 'error')
        return redirect(url_for('ver_datos'))
        
    if request.method == 'POST':
        nombre = request.form['nombre']
        apellido = request.form['apellido']
        cedula = request.form['cedula']
        ano_cursado = request.form['ano_cursado']
        rep_nombre = request.form['rep_nombre']
        rep_correo = request.form['rep_correo']
        rep_apellido = request.form.get('rep_apellido', 'No registrado')
        rep_telefono = request.form.get('rep_telefono', 'No registrado')
        
        conn = db_connection.get_connection()
        c = conn.cursor()
        c.execute('''
            UPDATE inscripciones 
            SET nombre = %s, apellido = %s, cedula = %s, ano_cursado = %s,
                rep_nombre = %s, rep_correo = %s, rep_apellido = %s, rep_telefono = %s
            WHERE id = %s
        ''', (nombre, apellido, cedula, ano_cursado, rep_nombre, rep_correo, rep_apellido, rep_telefono, id))
        conn.commit()
        conn.close()
        
        flash('Inscripción de estudiante actualizada con éxito.', 'success')
        return redirect(url_for('ver_datos'))
        
    return render_template('editar_inscripcion.html', ins=ins)

@app.route('/estudiante/<int:id>')
def ficha_estudiante(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))

    conn = db_connection.get_connection()
    c = conn.cursor(dictionary=True)
    asegurar_tabla_archivos(c)
    c.execute('SELECT * FROM inscripciones WHERE id = %s', (id,))
    estudiante = c.fetchone()

    if not estudiante:
        conn.close()
        flash('Inscripción no encontrada.', 'error')
        return redirect(url_for('ver_datos'))

    c.execute(
        'SELECT * FROM archivos_inscripcion WHERE inscripcion_id = %s ORDER BY tipo, creado_en',
        (id,)
    )
    archivos_estudiante = c.fetchall()
    conn.close()

    foto_estudiante = next(
        (archivo for archivo in archivos_estudiante if archivo['tipo'] == 'Foto tipo carnet del estudiante'),
        None
    )
    return render_template(
        'ficha_estudiante.html',
        estudiante=estudiante,
        archivos=archivos_estudiante,
        foto_estudiante=foto_estudiante
    )

@app.route('/archivo_inscripcion/<int:id>')
def ver_archivo_inscripcion(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))

    conn = db_connection.get_connection()
    c = conn.cursor(dictionary=True)
    asegurar_tabla_archivos(c)
    c.execute('SELECT nombre_archivo, nombre_original, extension FROM archivos_inscripcion WHERE id = %s', (id,))
    archivo = c.fetchone()
    conn.close()

    if not archivo:
        abort(404)

    return send_from_directory(
        UPLOAD_FOLDER,
        archivo['nombre_archivo'],
        as_attachment=archivo['extension'].lower() == '.pdf',
        download_name=archivo['nombre_original']
    )

@app.route('/eliminar_inscripcion/<int:id>')
def eliminar_inscripcion(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    rol = session.get('rol')
    if rol not in ['desarrollador', 'directora']:
        flash('Acceso denegado: El personal de administración no tiene permisos para eliminar registros.', 'error')
        return redirect(url_for('ver_datos'))
        
    conn = db_connection.get_connection()
    c = conn.cursor()
    asegurar_tabla_archivos(c)
    c.execute('SELECT nombre_archivo FROM archivos_inscripcion WHERE inscripcion_id = %s', (id,))
    archivos = c.fetchall()
    c.execute('DELETE FROM inscripciones WHERE id = %s', (id,))
    conn.commit()
    conn.close()

    for archivo in archivos:
        ruta_archivo = UPLOAD_FOLDER / archivo[0]
        try:
            ruta_archivo.unlink(missing_ok=True)
        except OSError:
            app.logger.exception('No se pudo eliminar el archivo adjunto %s', ruta_archivo)
    
    flash('Inscripción eliminada correctamente.', 'success')
    return redirect(url_for('ver_datos'))

@app.route('/inscripcion', methods=['GET', 'POST'])
def inscripcion():
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        archivos_subidos = []
        for campo, (tipo, extensiones_permitidas) in ARCHIVOS_INSCRIPCION.items():
            archivo = request.files.get(campo)
            if not archivo or not archivo.filename:
                continue

            nombre_original = secure_filename(archivo.filename)
            extension = Path(nombre_original).suffix.lower()
            if not nombre_original or extension not in extensiones_permitidas:
                flash(f'El archivo seleccionado para "{tipo}" tiene un formato no permitido.', 'error')
                return redirect(url_for('inscripcion'))

            archivos_subidos.append((archivo, tipo, nombre_original, extension))

        nombres_est = request.form['nombres_estudiante']
        apellidos_est = request.form['apellidos_estudiante']
        
        grado_num = request.form['grado']
        grado_nombres = {
            '1': '1er Grado',
            '2': '2do Grado',
            '3': '3er Grado',
            '4': '4to Grado',
            '5': '5to Grado'
        }
        grado_str = grado_nombres.get(grado_num, f"{grado_num}° Grado")
        seccion = request.form['seccion']
        ano_cursado = f"{grado_str} - Sección {seccion}"
        
        cedula = request.form['cedula_estudiantil']
        rep_nombre = request.form['nombre_madre']
        rep_apellido = request.form.get('nombre_padre', 'No registrado')
        rep_correo = request.form['cedula_madre']
        rep_telefono = request.form.get('cedula_padre', 'No registrado')
        
        rutas_guardadas = []
        conn = None
        try:
            UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
            conn = db_connection.get_connection()
            c = conn.cursor()
            asegurar_tabla_archivos(c)
            c.execute('''
                INSERT INTO inscripciones
                (nombre, apellido, ano_cursado, cedula, rep_nombre, rep_apellido, rep_correo, rep_telefono)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (nombres_est, apellidos_est, ano_cursado, cedula, rep_nombre, rep_apellido, rep_correo, rep_telefono))
            inscripcion_id = c.lastrowid

            for archivo, tipo, nombre_original, extension in archivos_subidos:
                nombre_guardado = f'{uuid4().hex}{extension}'
                ruta_archivo = UPLOAD_FOLDER / nombre_guardado
                rutas_guardadas.append(ruta_archivo)
                archivo.save(ruta_archivo)
                c.execute('''
                    INSERT INTO archivos_inscripcion
                    (inscripcion_id, tipo, nombre_archivo, nombre_original, extension)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (inscripcion_id, tipo, nombre_guardado, nombre_original, extension))

            conn.commit()
        except (OSError, Error):
            if conn:
                conn.rollback()
            for ruta_archivo in rutas_guardadas:
                try:
                    ruta_archivo.unlink(missing_ok=True)
                except OSError:
                    app.logger.exception('No se pudo limpiar el archivo adjunto %s', ruta_archivo)
            app.logger.exception('No se pudo guardar la inscripción y sus archivos adjuntos.')
            flash('No se pudo guardar la inscripción o uno de sus archivos. Inténtelo nuevamente.', 'error')
            return redirect(url_for('inscripcion'))
        finally:
            if conn:
                conn.close()
        
        flash('Inscripción registrada con éxito.', 'success')
        return redirect(url_for('dashboard'))
        
    return render_template('inscripcion.html')

@app.route('/ver_datos')
def ver_datos():
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    search_query = request.args.get('q', '')
    grado_filter = request.args.get('grado', '')
    seccion_filter = request.args.get('seccion', '')
    
    conn = db_connection.get_connection()
    c = conn.cursor(dictionary=True)
    
    # Construcción de consulta para inscripciones
    query_ins = 'SELECT * FROM inscripciones WHERE 1=1'
    params_ins = []
    
    if search_query:
        query_ins += ' AND (nombre LIKE %s OR apellido LIKE %s OR cedula LIKE %s)'
        search_param = f'%{search_query}%'
        params_ins.extend([search_param, search_param, search_param])
        
    if grado_filter:
        query_ins += ' AND ano_cursado LIKE %s'
        params_ins.append(f'%{grado_filter}%Grado%')
        
    if seccion_filter:
        query_ins += ' AND ano_cursado LIKE %s'
        params_ins.append(f'%Sección {seccion_filter}%')
        
    query_ins += ' ORDER BY ano_cursado, apellido, nombre'
    c.execute(query_ins, params_ins)
    inscripciones = c.fetchall()
    
    conn.close()
    
    return render_template('ver_datos.html', 
                           inscripciones=inscripciones,
                           search_query=search_query,
                           grado_filter=grado_filter,
                           seccion_filter=seccion_filter)
    
if __name__ == '__main__':
    try:
        test_conn = db_connection.get_connection()
        print("[OK] Conexion con MySQL establecida correctamente.")
    except Exception as e:
        print("\n" + "=" * 65)
        print(f"[ERROR] Error al conectar a MySQL: {e}")
        print("Por favor, verifica lo siguiente:")
        print("1. Abre el panel de XAMPP e inicia el servicio MySQL (Start).")
        print("2. Asegurate de tener la base de datos 'escuela_ebngru' o 'escuela_db'.")
        print("=" * 65)
        try:
            input("\nPresiona Enter para salir...")
        except Exception:
            pass
        raise SystemExit(1)

    app.run(host='0.0.0.0', port=5000)
