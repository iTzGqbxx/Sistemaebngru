
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = 'EBNGRU_secret_key_super_secure'

DB_NAME = 'escuela.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Tabla para documentos ("Registro de Planilla" y "Registro de completación")
    c.execute('''
        CREATE TABLE IF NOT EXISTS documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_documento TEXT NOT NULL,
            nombre TEXT NOT NULL,
            apellido TEXT NOT NULL,
            ano_cursado TEXT NOT NULL,
            cedula TEXT NOT NULL,
            literal TEXT
        )
    ''')
    
    # Tabla para inscripciones de estudiantes
    c.execute('''
        CREATE TABLE IF NOT EXISTS inscripciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            apellido TEXT NOT NULL,
            ano_cursado TEXT NOT NULL,
            cedula TEXT NOT NULL,
            rep_nombre TEXT NOT NULL,
            rep_apellido TEXT NOT NULL,
            rep_correo TEXT NOT NULL,
            rep_telefono TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# Initialize DB on startup
init_db()

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
        
        if usuario == 'administracionGRU' and password == 'EBNGRU':
            session['usuario'] = usuario
            return redirect(url_for('dashboard'))
        else:
            flash('Usuario o contraseña incorrectos.', 'error')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('usuario', None)
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
        
    if request.method == 'POST':
        tipo_documento = request.form['tipo_documento']
        nombre = request.form['nombre']
        apellido = request.form['apellido']
        ano_cursado = request.form['ano_cursado']
        cedula = 'V-' + request.form['cedula']
        literal = request.form.get('literal', None)
        
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''
            INSERT INTO documentos (tipo_documento, nombre, apellido, ano_cursado, cedula, literal)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (tipo_documento, nombre, apellido, ano_cursado, cedula, literal))
        conn.commit()
        conn.close()
        
        flash('Documento registrado con éxito.', 'success')
        return redirect(url_for('dashboard'))
        
    return render_template('documentos.html')

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
        
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''
            INSERT INTO inscripciones 
            (nombre, apellido, ano_cursado, cedula, rep_nombre, rep_apellido, rep_correo, rep_telefono)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
        
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute('SELECT * FROM documentos')
    documentos = c.fetchall()
    
    c.execute('SELECT * FROM inscripciones')
    inscripciones = c.fetchall()
    
    conn.close()
    
    return render_template('ver_datos.html', documentos=documentos, inscripciones=inscripciones)
    
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
