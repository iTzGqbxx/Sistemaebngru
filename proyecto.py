import mysql.connector
from mysql.connector import Error
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = 'EBNGRU_secret_key_super_secure'

class DatabaseConnection:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseConnection, cls).__new__(cls)
            cls._instance._initialize_connection()
        return cls._instance

    def _initialize_connection(self):
        try:
            self.connection = mysql.connector.connect(
                user="root",
                password="",
                host="localhost",
                database="escuela_db",
                port="3306"
            )
        except Error as e:
            print(f"Error al conectar a MySQL: {e}")
            raise

    def get_connection(self):
        if not self.connection.is_connected():
            self._initialize_connection()
        return self.connection

    def close_connection(self):
        if self.connection.is_connected():
            self.connection.close()

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
        
        if usuario == 'desarrollador' and password == 'developerGRU':
            session['usuario'] = usuario
            session['rol'] = 'desarrollador'
            return redirect(url_for('dashboard'))
        elif usuario == 'directoraGRU' and password == 'directoraEBNGRU':
            session['usuario'] = usuario
            session['rol'] = 'directora'
            return redirect(url_for('dashboard'))
        elif usuario == 'administracionGRU' and password == 'EBNGRU':
            session['usuario'] = usuario
            session['rol'] = 'administracion'
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

@app.route('/documentos', methods=['GET', 'POST'])
def documentos():
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    rol = session.get('rol')
    
    # Documentos permitidos para administración
    documentos_permitidos_admin = [
        'Planilla de Inscripción',
        'Constancia de Estudio',
        'Constancia de Cupo',
        'Constancia de Inscripción'
    ]
        
    if request.method == 'POST':
        tipo_documento = request.form['tipo_documento']
        
        # Validar tipo de documento si es rol administracion
        if rol == 'administracion' and tipo_documento not in documentos_permitidos_admin:
            flash('Acceso denegado: No tiene permisos para registrar este tipo de documento.', 'error')
            return redirect(url_for('dashboard'))
            
        nombre = request.form['nombre']
        apellido = request.form['apellido']
        ano_cursado = request.form['ano_cursado']
        cedula = 'V-' + request.form['cedula']
        literal = request.form.get('literal', None)
        
        conn = db_connection.get_connection()
        c = conn.cursor()
        c.execute('''
            INSERT INTO documentos (tipo_documento, nombre, apellido, ano_cursado, cedula, literal)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (tipo_documento, nombre, apellido, ano_cursado, cedula, literal))
        conn.commit()
        conn.close()
        
        flash('Documento registrado con éxito.', 'success')
        return redirect(url_for('dashboard'))
        
    return render_template('documentos.html', allowed_types=documentos_permitidos_admin if rol == 'administracion' else None)

@app.route('/editar_documento/<int:id>', methods=['GET', 'POST'])
def editar_documento(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    rol = session.get('rol')
    
    conn = db_connection.get_connection()
    c = conn.cursor(dictionary=True)
    c.execute('SELECT * FROM documentos WHERE id = %s', (id,))
    doc = c.fetchone()
    conn.close()
    
    if not doc:
        flash('Documento no encontrado.', 'error')
        return redirect(url_for('ver_datos'))
        
    documentos_permitidos_admin = [
        'Planilla de Inscripción',
        'Constancia de Estudio',
        'Constancia de Cupo',
        'Constancia de Inscripción'
    ]
    
    if rol == 'administracion' and doc['tipo_documento'] not in documentos_permitidos_admin:
        flash('Acceso denegado: No tiene permisos para modificar este tipo de documento.', 'error')
        return redirect(url_for('ver_datos'))
        
    if request.method == 'POST':
        tipo_documento = request.form['tipo_documento']
        nombre = request.form['nombre']
        apellido = request.form['apellido']
        ano_cursado = request.form['ano_cursado']
        
        cedula_input = request.form['cedula']
        if not cedula_input.startswith('V-'):
            cedula = 'V-' + cedula_input
        else:
            cedula = cedula_input
            
        literal = request.form.get('literal', None)
        
        if rol == 'administracion' and tipo_documento not in documentos_permitidos_admin:
            flash('Acceso denegado: No puede cambiar el documento a un tipo no autorizado.', 'error')
            return redirect(url_for('ver_datos'))
            
        conn = db_connection.get_connection()
        c = conn.cursor()
        c.execute('''
            UPDATE documentos 
            SET tipo_documento = %s, nombre = %s, apellido = %s, ano_cursado = %s, cedula = %s, literal = %s
            WHERE id = %s
        ''', (tipo_documento, nombre, apellido, ano_cursado, cedula, literal, id))
        conn.commit()
        conn.close()
        
        flash('Documento modificado con éxito.', 'success')
        return redirect(url_for('ver_datos'))
        
    return render_template('editar_documento.html', doc=doc, allowed_types=documentos_permitidos_admin if rol == 'administracion' else None)

@app.route('/eliminar_documento/<int:id>')
def eliminar_documento(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    rol = session.get('rol')
    if rol not in ['directora', 'desarrollador']:
        flash('Acceso denegado: Solo la Directora o el Desarrollador pueden eliminar documentos.', 'error')
        return redirect(url_for('ver_datos'))
        
    conn = db_connection.get_connection()
    c = conn.cursor()
    c.execute('DELETE FROM documentos WHERE id = %s', (id,))
    conn.commit()
    conn.close()
    
    flash('Documento eliminado correctamente.', 'success')
    return redirect(url_for('ver_datos'))

@app.route('/eliminar_inscripcion/<int:id>')
def eliminar_inscripcion(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    rol = session.get('rol')
    if rol != 'desarrollador':
        flash('Acceso denegado: Únicamente el Desarrollador puede eliminar inscripciones.', 'error')
        return redirect(url_for('ver_datos'))
        
    conn = db_connection.get_connection()
    c = conn.cursor()
    c.execute('DELETE FROM inscripciones WHERE id = %s', (id,))
    conn.commit()
    conn.close()
    
    flash('Inscripción eliminada correctamente.', 'success')
    return redirect(url_for('ver_datos'))

@app.route('/inscripcion', methods=['GET', 'POST'])
def inscripcion():
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
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
        
        conn = db_connection.get_connection()
        c = conn.cursor()
        c.execute('''
            INSERT INTO inscripciones 
            (nombre, apellido, ano_cursado, cedula, rep_nombre, rep_apellido, rep_correo, rep_telefono)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (nombres_est, apellidos_est, ano_cursado, cedula, rep_nombre, rep_apellido, rep_correo, rep_telefono))
        conn.commit()
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
        query_ins += ' AND ano_cursado LIKE ?'
        params_ins.append(f'%{grado_filter}%Grado%')
        
    if seccion_filter:
        query_ins += ' AND ano_cursado LIKE ?'
        params_ins.append(f'%Sección {seccion_filter}%')
        
    c.execute(query_ins, params_ins)
    inscripciones = c.fetchall()
    
    # Construcción de consulta para documentos
    query_doc = 'SELECT * FROM documentos WHERE 1=1'
    params_doc = []
    
    if search_query:
        query_doc += ' AND (nombre LIKE %s OR apellido LIKE %s OR cedula LIKE %s)'
        search_param = f'%{search_query}%'
        params_doc.extend([search_param, search_param, search_param])
        
    if grado_filter:
        query_doc += ' AND ano_cursado LIKE ?'
        params_doc.append(f'%{grado_filter}%') # En documentos el formato puede variar un poco, usamos genérico
        
    c.execute(query_doc, params_doc)
    documentos = c.fetchall()
    
    conn.close()
    
    return render_template('ver_datos.html', 
                           documentos=documentos, 
                           inscripciones=inscripciones,
                           search_query=search_query,
                           grado_filter=grado_filter,
                           seccion_filter=seccion_filter)
    
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
