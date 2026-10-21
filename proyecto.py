import sys
import re
import hmac
from hashlib import sha1, sha256
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import mysql.connector
import pymupdf
from mysql.connector import Error
from flask import Flask, abort, render_template, request, redirect, url_for, session, flash, send_file, send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.security import check_password_hash, generate_password_hash

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

app = Flask(__name__)
app.secret_key = 'EBNGRU_secret_key_super_secure'
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024
UPLOAD_FOLDER = Path(app.instance_path) / 'uploads'
USUARIOS_GESTION_EXPEDIENTES = {'desarrollador', 'directora', 'directoraGRU'}
ROLES_ADMINISTRACION = {'administracion', 'administrador', 'administracionGRU'}
GRADOS_CURSADO = ('1er Grado', '2do Grado', '3er Grado', '4to Grado', '5to Grado')
SECCIONES = ('A', 'B', 'C', 'D')
CAMPOS_EDITABLES = {
    'cedula': ('cedula', 'Cédula estudiantil', True),
    'nombre': ('nombre', 'Nombres del estudiante', True),
    'apellido': ('apellido', 'Apellidos del estudiante', True),
    'ano_cursado': ('ano_cursado', 'Grado y sección actuales', True),
    'repMadre_nombre': ('repMadre_nombre', 'Nombres de la madre', True),
    'repMadre_apellido': ('repMadre_apellido', 'Apellidos de la madre', True),
    'repMadre_cedula': ('repMadre_cedula', 'Cédula de la madre', True),
    'repPadre_nombre': ('repPadre_nombre', 'Nombres del padre', False),
    'repPadre_apellido': ('repPadre_apellido', 'Apellidos del padre', False),
    'repPadre_cedula': ('repPadre_cedula', 'Cédula del padre', False),
}

ARCHIVOS_INSCRIPCION = {
    'doc_partida_nacimiento': ('Partida de nacimiento del estudiante', {'.pdf', '.jpg', '.jpeg', '.png', '.webp'}),
    'doc_cedula_estudiante': ('Copia de cédula del estudiante (de disponer una propia)', {'.pdf', '.jpg', '.jpeg', '.png', '.webp'}),
    'doc_carton_vacunas': ('Copia de cartón de vacunas', {'.pdf', '.jpg', '.jpeg', '.png', '.webp'}),
    'doc_cedula_representante': ('Copia de cédula del representante', {'.pdf', '.jpg', '.jpeg', '.png', '.webp'}),
    'doc_rif_representante': ('Copia del RIF actualizado', {'.pdf', '.jpg', '.jpeg', '.png', '.webp'}),
    'foto_estudiante': ('Foto tipo carnet del estudiante', {'.jpg', '.jpeg', '.png', '.webp'}),
    'foto_representante': ('Foto tipo carnet del representante', {'.jpg', '.jpeg', '.png', '.webp'}),
}


def puede_gestionar_expedientes():
    return session.get('usuario') in USUARIOS_GESTION_EXPEDIENTES


def puede_editar_expedientes():
    return puede_gestionar_expedientes() or session.get('rol') in ROLES_ADMINISTRACION


def verificar_password(password, password_guardado):
    if password_guardado.startswith(('scrypt:', 'pbkdf2:')):
        return check_password_hash(password_guardado, password)

    if re.fullmatch(r'\*[0-9a-fA-F]{40}', password_guardado):
        password_mysql = '*' + sha1(
            sha1(password.encode('utf-8')).digest()
        ).hexdigest().upper()
        return hmac.compare_digest(password_mysql, password_guardado.upper())

    if re.fullmatch(r'[0-9a-fA-F]{64}', password_guardado):
        password_sha256 = sha256(password.encode('utf-8')).hexdigest()
        return hmac.compare_digest(password_sha256, password_guardado.lower())

    return hmac.compare_digest(password_guardado, password)


def separar_ubicacion_academica(valor):
    partes = valor.split(' - Sección ', 1)
    if len(partes) == 2 and partes[0] in GRADOS_CURSADO and partes[1] in SECCIONES:
        return partes
    return '', ''


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
    if request.endpoint == 'editar_archivos_inscripcion' and 'usuario' in session:
        flash('Los archivos adjuntos superan el límite total de 32 MB.', 'error')
        return redirect(url_for('editar_archivos_inscripcion', id=request.view_args['id']))
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
        try:
            c = conn.cursor(dictionary=True)
            c.execute(
                'SELECT id, usuario, password, rol FROM usuarios WHERE usuario = %s',
                (usuario,)
            )
            usuario_db = c.fetchone()
            autenticado = usuario_db is not None and verificar_password(
                password,
                usuario_db['password']
            )

            if autenticado:
                password_guardado = usuario_db['password']
                if not password_guardado.startswith(('scrypt:', 'pbkdf2:')):
                    c.execute(
                        'UPDATE usuarios SET password = %s WHERE id = %s',
                        (generate_password_hash(password), usuario_db['id'])
                    )
                    conn.commit()
        finally:
            conn.close()

        if autenticado:
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
    puede_gestionar = puede_gestionar_expedientes()
    mostrar_boton_eliminar = puede_gestionar or session.get('rol') in {
        'administracion',
        'administrador',
        'administracionGRU'
    }
    return render_template(
        'dashboard.html',
        puede_gestionar_expedientes=puede_gestionar,
        puede_editar_expedientes=puede_editar_expedientes(),
        mostrar_boton_eliminar=mostrar_boton_eliminar
    )

@app.route('/eliminar_estudiante')
def seleccionar_estudiante_eliminar():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    if not puede_gestionar_expedientes():
        abort(403)

    conn = db_connection.get_connection()
    c = conn.cursor(dictionary=True)
    c.execute(
        'SELECT id, nombre, apellido, ano_cursado FROM inscripciones '
        'ORDER BY ano_cursado, apellido, nombre'
    )
    inscripciones = c.fetchall()
    conn.close()
    return render_template('eliminar_estudiante.html', inscripciones=inscripciones)

@app.route('/editar_inscripcion/<int:id>', methods=['GET', 'POST'])
def editar_inscripcion(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))

    if not puede_editar_expedientes():
        abort(403)

    campo = request.args.get('campo')
    if campo not in CAMPOS_EDITABLES:
        abort(404)

    conn = db_connection.get_connection()
    c = conn.cursor(dictionary=True)
    c.execute('SELECT * FROM inscripciones WHERE id = %s', (id,))
    ins = c.fetchone()
    conn.close()

    if not ins:
        flash('Inscripción no encontrada.', 'error')
        return redirect(url_for('ver_datos'))

    columna, etiqueta, requerido = CAMPOS_EDITABLES[campo]
    grado_actual, seccion_actual = separar_ubicacion_academica(ins[columna] or '')
    if request.method == 'POST':
        if campo == 'ano_cursado':
            grado = request.form.get('grado', '')
            seccion = request.form.get('seccion', '')
            if grado not in GRADOS_CURSADO or seccion not in SECCIONES:
                flash('Seleccione un grado y una sección válidos.', 'error')
                return render_template(
                    'editar_campo.html',
                    ins=ins,
                    campo=campo,
                    etiqueta=etiqueta,
                    valor=ins[columna],
                    requerido=requerido,
                    grados_cursado=GRADOS_CURSADO,
                    secciones=SECCIONES,
                    grado_actual=grado if grado in GRADOS_CURSADO else grado_actual,
                    seccion_actual=seccion if seccion in SECCIONES else seccion_actual
                )
            valor = f'{grado} - Sección {seccion}'
        else:
            valor = request.form.get('valor', '').strip()
        es_cedula = columna in {'cedula', 'repMadre_cedula', 'repPadre_cedula'}
        if requerido and not valor:
            flash(f'El campo "{etiqueta}" no puede quedar vacío.', 'error')
            return render_template(
                'editar_campo.html',
                ins=ins,
                campo=campo,
                etiqueta=etiqueta,
                valor=ins[columna],
                requerido=requerido,
                grados_cursado=GRADOS_CURSADO,
                secciones=SECCIONES,
                grado_actual=grado_actual,
                seccion_actual=seccion_actual
            )
        if es_cedula and valor and not re.fullmatch(r'V[0-9]+', valor.upper()):
            flash(f'Ingrese una cédula válida en el campo "{etiqueta}" (por ejemplo, V319458534).', 'error')
            return render_template(
                'editar_campo.html',
                ins=ins,
                campo=campo,
                etiqueta=etiqueta,
                valor=valor.upper(),
                requerido=requerido,
                grados_cursado=GRADOS_CURSADO,
                secciones=SECCIONES,
                grado_actual=grado_actual,
                seccion_actual=seccion_actual
            )
        if es_cedula and valor:
            valor = valor.upper()
        if not requerido and not valor:
            valor = 'No registrado'

        conn = db_connection.get_connection()
        c = conn.cursor()
        c.execute(
            f'UPDATE inscripciones SET {columna} = %s WHERE id = %s',
            (valor, id)
        )
        conn.commit()
        conn.close()
        flash(f'{etiqueta} actualizado correctamente.', 'success')
        return redirect(url_for('ficha_estudiante', id=id))

    return render_template(
        'editar_campo.html',
        ins=ins,
        campo=campo,
        etiqueta=etiqueta,
        valor=ins[columna],
        requerido=requerido,
        grados_cursado=GRADOS_CURSADO,
        secciones=SECCIONES,
        grado_actual=grado_actual,
        seccion_actual=seccion_actual
    )

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
        foto_estudiante=foto_estudiante,
        puede_gestionar_expedientes=puede_gestionar_expedientes(),
        puede_editar_expedientes=puede_editar_expedientes()
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

    if archivo['extension'].lower() == '.pdf' and request.args.get('vista') == 'miniatura':
        nombre_archivo = Path(archivo['nombre_archivo'])
        if nombre_archivo.name != archivo['nombre_archivo']:
            app.logger.error('Nombre de PDF adjunto no válido en el registro %s.', id)
            abort(400)

        ruta_archivo = UPLOAD_FOLDER / nombre_archivo
        if not ruta_archivo.is_file():
            abort(404)

        try:
            with pymupdf.open(ruta_archivo) as documento:
                if documento.page_count == 0:
                    abort(404)
                pixmap = documento[0].get_pixmap(
                    matrix=pymupdf.Matrix(0.8, 0.8),
                    alpha=False
                )
                imagen = BytesIO(pixmap.tobytes('png'))
        except (pymupdf.FileDataError, pymupdf.EmptyFileError, OSError, RuntimeError):
            app.logger.exception('No se pudo generar la miniatura del PDF adjunto %s.', id)
            abort(500)

        imagen.seek(0)
        return send_file(imagen, mimetype='image/png', max_age=300)

    return send_from_directory(
        UPLOAD_FOLDER,
        archivo['nombre_archivo'],
        as_attachment=archivo['extension'].lower() == '.pdf',
        download_name=archivo['nombre_original']
    )

@app.route('/eliminar_archivo_inscripcion/<int:id>', methods=['POST'])
def eliminar_archivo_inscripcion(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))
    if not puede_editar_expedientes():
        abort(403)

    conn = db_connection.get_connection()
    try:
        c = conn.cursor(dictionary=True)
        asegurar_tabla_archivos(c)
        c.execute(
            'SELECT inscripcion_id, nombre_archivo, tipo FROM archivos_inscripcion WHERE id = %s',
            (id,)
        )
        archivo = c.fetchone()
        if not archivo:
            abort(404)

        nombre_archivo = Path(archivo['nombre_archivo'])
        if nombre_archivo.name != archivo['nombre_archivo']:
            app.logger.error('Nombre de archivo adjunto no válido en el registro %s.', id)
            abort(400)

        c.execute('DELETE FROM archivos_inscripcion WHERE id = %s', (id,))
        conn.commit()
    except Error:
        conn.rollback()
        app.logger.exception('No se pudo eliminar el registro del archivo adjunto %s.', id)
        flash('No se pudo quitar el archivo del expediente. Inténtelo nuevamente.', 'error')
        return redirect(url_for('ver_datos'))
    finally:
        conn.close()

    try:
        (UPLOAD_FOLDER / nombre_archivo).unlink(missing_ok=True)
    except OSError:
        app.logger.exception('No se pudo eliminar el archivo adjunto %s', nombre_archivo)
        flash('Se quitó el archivo del expediente, pero no se pudo eliminar el archivo almacenado.', 'error')
        return redirect(url_for('ficha_estudiante', id=archivo['inscripcion_id']))

    flash(f'Se quitó "{archivo["tipo"]}" del expediente.', 'success')
    return redirect(url_for('ficha_estudiante', id=archivo['inscripcion_id']))

@app.route('/editar_archivos_inscripcion/<int:id>', methods=['GET', 'POST'])
def editar_archivos_inscripcion(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))
    if not puede_editar_expedientes():
        abort(403)

    conn = db_connection.get_connection()
    c = conn.cursor(dictionary=True)
    c.execute('SELECT id, nombre, apellido FROM inscripciones WHERE id = %s', (id,))
    estudiante = c.fetchone()
    if not estudiante:
        conn.close()
        flash('Inscripción no encontrada.', 'error')
        return redirect(url_for('ver_datos'))

    asegurar_tabla_archivos(c)
    c.execute(
        'SELECT id, tipo, nombre_archivo, nombre_original FROM archivos_inscripcion '
        'WHERE inscripcion_id = %s ORDER BY id DESC',
        (id,)
    )
    archivos = c.fetchall()
    conn.close()

    tipos_anteriores = {
        'Copia de cédula del estudiante': 'Copia de cédula del estudiante (de disponer una propia)'
    }
    archivos_por_tipo = {}
    tipos_actuales = {tipo for tipo, _ in ARCHIVOS_INSCRIPCION.values()}
    for archivo in archivos:
        tipo = archivo['tipo']
        tipo_canonico = tipos_anteriores.get(tipo, tipo)
        if tipo_canonico in tipos_actuales and tipo_canonico not in archivos_por_tipo:
            archivos_por_tipo[tipo_canonico] = archivo

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
                return redirect(url_for('editar_archivos_inscripcion', id=id))
            archivos_subidos.append((archivo, tipo, nombre_original, extension))

        if not archivos_subidos:
            flash('Seleccione al menos un archivo para agregar o reemplazar.', 'error')
            return redirect(url_for('editar_archivos_inscripcion', id=id))

        rutas_nuevas = []
        rutas_reemplazadas = []
        conn = None
        try:
            UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
            conn = db_connection.get_connection()
            c = conn.cursor()
            asegurar_tabla_archivos(c)
            for archivo, tipo, nombre_original, extension in archivos_subidos:
                nombre_guardado = f'{uuid4().hex}{extension}'
                ruta_guardada = UPLOAD_FOLDER / nombre_guardado
                rutas_nuevas.append(ruta_guardada)
                archivo.save(ruta_guardada)

                archivo_existente = archivos_por_tipo.get(tipo)
                if archivo_existente:
                    c.execute(
                        'UPDATE archivos_inscripcion SET tipo = %s, nombre_archivo = %s, '
                        'nombre_original = %s, extension = %s WHERE id = %s',
                        (tipo, nombre_guardado, nombre_original, extension, archivo_existente['id'])
                    )
                    rutas_reemplazadas.append(UPLOAD_FOLDER / archivo_existente['nombre_archivo'])
                else:
                    c.execute(
                        'INSERT INTO archivos_inscripcion '
                        '(inscripcion_id, tipo, nombre_archivo, nombre_original, extension) '
                        'VALUES (%s, %s, %s, %s, %s)',
                        (id, tipo, nombre_guardado, nombre_original, extension)
                    )
            conn.commit()
        except (OSError, Error):
            if conn:
                conn.rollback()
            for ruta in rutas_nuevas:
                try:
                    ruta.unlink(missing_ok=True)
                except OSError:
                    app.logger.exception('No se pudo limpiar el archivo adjunto %s', ruta)
            app.logger.exception('No se pudieron actualizar los archivos del expediente %s.', id)
            flash('No se pudieron guardar los archivos. Inténtelo nuevamente.', 'error')
            return redirect(url_for('editar_archivos_inscripcion', id=id))
        finally:
            if conn:
                conn.close()

        for ruta in rutas_reemplazadas:
            try:
                ruta.unlink(missing_ok=True)
            except OSError:
                app.logger.exception('No se pudo retirar el archivo adjunto reemplazado %s', ruta)
        flash('Los archivos del expediente se actualizaron correctamente.', 'success')
        return redirect(url_for('ficha_estudiante', id=id))

    return render_template(
        'editar_archivos.html',
        estudiante=estudiante,
        archivos_por_tipo=archivos_por_tipo,
        archivos_inscripcion=ARCHIVOS_INSCRIPCION
    )

@app.route('/eliminar_inscripcion/<int:id>', methods=['POST'])
def eliminar_inscripcion(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    if not puede_gestionar_expedientes():
        abort(403)
        
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
    return redirect(url_for('seleccionar_estudiante_eliminar'))

@app.route('/inscripcion', methods=['GET', 'POST'])
def inscripcion():
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        campos_cedula = (
            ('cedula_estudiantil', 'la cédula del estudiante', True),
            ('repMadre_cedula', 'la cédula de la madre', True),
            ('repPadre_cedula', 'la cédula del padre', False),
        )
        for campo, etiqueta, requerido in campos_cedula:
            valor = request.form.get(campo, '').strip()
            if (requerido and not valor) or (valor and not re.fullmatch(r'V[0-9]+', valor.upper())):
                flash(f'Ingrese una cédula válida en {etiqueta} (por ejemplo, V319458534).', 'error')
                return redirect(url_for('inscripcion'))

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
        
        cedula = request.form['cedula_estudiantil'].strip().upper()
        rep_madre_nombre = request.form['repMadre_nombre'].strip()
        rep_madre_apellido = request.form['repMadre_apellido'].strip()
        rep_madre_cedula = request.form['repMadre_cedula'].strip().upper()
        rep_padre_nombre = request.form.get('repPadre_nombre', '').strip() or 'No registrado'
        rep_padre_apellido = request.form.get('repPadre_apellido', '').strip() or 'No registrado'
        rep_padre_cedula = request.form.get('repPadre_cedula', '').strip().upper() or 'No registrado'
        
        rutas_guardadas = []
        conn = None
        try:
            UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
            conn = db_connection.get_connection()
            c = conn.cursor()
            asegurar_tabla_archivos(c)
            c.execute('''
                INSERT INTO inscripciones
                (nombre, apellido, ano_cursado, cedula, repMadre_nombre, repMadre_apellido,
                 repMadre_cedula, repPadre_nombre, repPadre_apellido, repPadre_cedula)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                nombres_est, apellidos_est, ano_cursado, cedula, rep_madre_nombre,
                rep_madre_apellido, rep_madre_cedula, rep_padre_nombre,
                rep_padre_apellido, rep_padre_cedula
            ))
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
        print("[OK] Conexión con MySQL establecida correctamente.")
    except Exception as e:
        print("\n" + "=" * 65)
        print(f"[ERROR] Error al conectar a MySQL: {e}")
        print("Por favor, verifica lo siguiente:")
        print("1. Abre el panel de XAMPP e inicia el servicio MySQL (Start).")
        print("2. Asegúrate de tener la base de datos 'escuela_ebngru' o 'escuela_db'.")
        print("=" * 65)
        try:
            input("\nPresiona Enter para salir...")
        except Exception:
            pass
        raise SystemExit(1)

    app.run(host='0.0.0.0', port=5000)
