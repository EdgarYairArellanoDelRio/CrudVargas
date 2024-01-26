from flask import (
    Flask, render_template, request, redirect, url_for, session, send_file, flash
)
from dotenv import load_dotenv
import os
import pymysql
from werkzeug.security import check_password_hash
import pandas as pd
from io import BytesIO

app = Flask(__name__, static_folder='static')
app.secret_key = os.urandom(24)  # Generar una clave secreta segura
load_dotenv()

# Configuración de la base de datos
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST')
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = os.getenv('MYSQL_DB')
app.config['MYSQL_CURSORCLASS'] = os.getenv('MYSQL_CURSORCLASS')

# Configuración SMTP
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT'))  # Convierte el puerto a entero
SMTP_USERNAME = os.getenv('SMTP_USERNAME')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
FROM_EMAIL = os.getenv('FROM_EMAIL')

# Conexión a la base de datos
mysql = pymysql.connect(
    host=app.config['MYSQL_HOST'],
    user=app.config['MYSQL_USER'],
    password=app.config['MYSQL_PASSWORD'],
    db=app.config['MYSQL_DB'],
    cursorclass=pymysql.cursors.DictCursor
)

@app.route('/')
def home():
   return render_template('login.html') 

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        try:
            connection = pymysql.connect(
                host=app.config['MYSQL_HOST'],
                user=app.config['MYSQL_USER'],
                password=app.config['MYSQL_PASSWORD'],
                db=app.config['MYSQL_DB'],
                cursorclass=pymysql.cursors.DictCursor
            )
            cursor = connection.cursor()

            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()

            if user and check_password_hash(user['password'], password):
                session['username'] = username
                session['rol'] = user['rol']

                if user['rol'] == 'admin':
                    return redirect(url_for('dashboard_admin'))
                elif user['rol'] == 'user':
                    return redirect(url_for('dashboard'))
                else:
                    return 'Rol no válido.'

            else:
                return 'Credenciales incorrectas. Inténtalo de nuevo.'

        except Exception as e:
            return f"Error: {str(e)}"

        finally:
            cursor.close()
            connection.close()

    return render_template('login.html')


@app.route('/dashboard_admin')
def dashboard_admin():
    # Verifica si el usuario tiene el rol adecuado
    if 'rol' in session and session['rol'] == 'admin':
        return render_template('admin_dashboard.html')
    else:
        return 'Acceso no autorizado.'

@app.route('/admin/users', methods=['GET', 'POST'])
def admin_users():
    if request.method == 'POST':
        # Lógica para agregar un nuevo usuario a la base de datos
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        rol = request.form['rol']

        # Encriptar la contraseña antes de almacenarla en la base de datos
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        # Aquí debes realizar la inserción del nuevo usuario en tu base de datos
        try:
            with mysql.cursor() as cursor:
                cursor.execute("INSERT INTO users (username, password, email, rol) VALUES (%s, %s, %s, %s)",
                               (username, hashed_password, email, rol))
            mysql.commit()

            flash('Usuario agregado exitosamente', 'success')
        except Exception as e:
            flash(f'Error al agregar usuario: {str(e)}', 'danger')

    # Obtener la lista de usuarios desde la base de datos
    try:
        with mysql.cursor() as cursor:
            # Obtener la lista de usuarios (esto es solo un ejemplo)
            sql = "SELECT id, username, email, rol FROM users"
            cursor.execute(sql)
            users = cursor.fetchall()
    except Exception as e:
        flash(f'Error al obtener la lista de usuarios: {str(e)}', 'danger')
        users = []

    return render_template('admin_users.html', users=users)

@app.route('/admin/users/eliminar/<int:user_id>', methods=['POST'])
def eliminar_usuario(user_id):
    # Lógica para eliminar el usuario con el ID proporcionado de la base de datos
    try:
        with mysql.cursor() as cursor:
            sql = "DELETE FROM users WHERE id=%s"
            cursor.execute(sql, (user_id,))
        mysql.commit()

        flash('Usuario eliminado exitosamente', 'success')
    except Exception as e:
        flash(f'Error al eliminar usuario: {str(e)}', 'danger')

    return redirect('/admin/users')  # Redirige a la página de administración de usuarios
    

@app.route('/descargarExcel')
def descargar_excel():
    try:
        connection = pymysql.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            db=app.config['MYSQL_DB'],
            cursorclass=pymysql.cursors.DictCursor
        )
        cursor = connection.cursor()

        # Obtener todos los viajes desde la base de datos
        cursor.execute('SELECT * FROM viajes')
        viajes = cursor.fetchall()

        # Crear un DataFrame de pandas con los datos
        df = pd.DataFrame(viajes)

        # Crear un objeto BytesIO para almacenar el archivo Excel
        excel_io = BytesIO()

        # Utilizar pandas para escribir el DataFrame en un archivo Excel
        df.to_excel(excel_io, index=False)

        # Posicionar el cursor al principio del objeto BytesIO
        excel_io.seek(0)

        # Cerrar la conexión a la base de datos
        cursor.close()
        connection.close()

        # Enviar el archivo Excel como una respuesta de descarga
        return send_file(
            excel_io,
            download_name='viajes.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True
        )

    except Exception as e:
        print(f"Error al descargar el archivo Excel: {str(e)}")
        return redirect(url_for('dashboard'))


@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        try:
            connection = pymysql.connect(
                host=app.config['MYSQL_HOST'],
                user=app.config['MYSQL_USER'],
                password=app.config['MYSQL_PASSWORD'],
                db=app.config['MYSQL_DB'],
                cursorclass=pymysql.cursors.DictCursor
            )
            cursor = connection.cursor()

            # Obtener el término de búsqueda desde la solicitud GET
            search_term = request.args.get('search', '')

            # Ajustar la consulta SQL para incluir la funcionalidad de búsqueda
            sql = f"SELECT * FROM viajes WHERE CONCAT(folio, fecha, origen_modelo, destinatario, chofer, no_pedido, folio_ida, placas, unidad) LIKE '%{search_term}%'"
            
            cursor.execute(sql)
            viajes = cursor.fetchall()

            return render_template('dashboard.html', nombre_de_usuario=session['username'], viajes=viajes)

        except Exception as e:
            print(f"Error al obtener los viajes: {str(e)}")
            return render_template('dashboard.html', nombre_de_usuario=session['username'], viajes=[])

        finally:
            cursor.close()
            connection.close()

    return redirect(url_for('login'))

# ...

@app.route('/agregarViaje', methods=['GET', 'POST'])
def agregarViaje():
    if request.method == 'POST':
        # Obtener datos del formulario
        folio = request.form['folio']
        fecha = request.form['fecha']
        # Agregar más campos según sea necesario

        try:
            # Validar los datos del formulario
            if not folio or not fecha:
                raise ValueError("Folio y fecha son campos requeridos")

            # Crear una conexión a la base de datos
            connection = pymysql.connect(
                host=app.config['MYSQL_HOST'],
                user=app.config['MYSQL_USER'],
                password=app.config['MYSQL_PASSWORD'],
                db=app.config['MYSQL_DB'],
                cursorclass=pymysql.cursors.DictCursor
            )

            # Crear un cursor para ejecutar consultas
            with connection.cursor() as cursor:
                # Ejecutar la consulta para insertar un nuevo viaje en la base de datos
                cursor.execute('''
                    INSERT INTO viajes (folio, fecha, origen_modelo, destinatario, chofer, no_pedido, folio_ida, placas, unidad, gastos_ocupados, gastos_depositados, diferencia, carga_1, carga_2, carga_3, total_litros, km_recorridos)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (
                    folio, fecha, request.form['origen_modelo'], request.form['destinatario'],
                    request.form['chofer'], request.form['no_pedido'], request.form['folio_ida'],
                    request.form['placas'], request.form['unidad'], request.form['gastos_ocupados'],
                    request.form['gastos_depositados'], request.form['diferencia'],
                    request.form['carga_1'], request.form['carga_2'], request.form['carga_3'],
                    request.form['total_litros'], request.form['km_recorridos']
                ))

            # Confirmar la transacción
            connection.commit()

            # Redirigir al usuario al dashboard después de agregar el viaje
            return redirect(url_for('dashboard'))

        except Exception as e:
            # Manejar la excepción, imprimir un mensaje de error, etc.
            print(f"Error: {str(e)}")

        finally:
            # Cerrar la conexión en el bloque finally
            if connection:
                connection.close()

    # Si el método no es POST o hay un error en el formulario, renderizar la plantilla del formulario
    return render_template('agregarViaje.html')

# ...
@app.route('/detalleViaje/<int:viaje_id>')
def detalleViaje(viaje_id):
    try:
        connection = pymysql.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            db=app.config['MYSQL_DB'],
            cursorclass=pymysql.cursors.DictCursor
        )
        cursor = connection.cursor()

        # Realizar la consulta para obtener los detalles del viaje con el ID proporcionado
        cursor.execute('SELECT * FROM viajes WHERE id = %s', (viaje_id,))
        viaje = cursor.fetchone()

        if viaje:
            return render_template('detalleViaje.html', viaje=viaje)
        else:
            return 'Viaje no encontrado.'

    except Exception as e:
        print(f"Error al obtener los detalles del viaje: {str(e)}")
        return 'Error al obtener los detalles del viaje.'

    finally:
        cursor.close()
        connection.close()

@app.route('/editarViaje/<int:viaje_id>', methods=['GET', 'POST'])
def editarViaje(viaje_id):
    if 'username' in session:
        connection = None
        cursor = None
        if request.method == 'GET':
            try:
                connection = pymysql.connect(
                    host=app.config['MYSQL_HOST'],
                    user=app.config['MYSQL_USER'],
                    password=app.config['MYSQL_PASSWORD'],
                    db=app.config['MYSQL_DB'],
                    cursorclass=pymysql.cursors.DictCursor
                )
                cursor = connection.cursor()

                # Realizar la consulta para obtener los detalles del viaje a editar
                cursor.execute('SELECT * FROM viajes WHERE id = %s', (viaje_id,))
                viaje = cursor.fetchone()

                return render_template('editarViaje.html', viaje=viaje)

            except Exception as e:
                print(f"Error al obtener los detalles del viaje: {str(e)}")
                return redirect(url_for('dashboard'))

            finally:
                cursor.close()
                connection.close()

        elif request.method == 'POST':
            try:
                connection = pymysql.connect(
                    host=app.config['MYSQL_HOST'],
                    user=app.config['MYSQL_USER'],
                    password=app.config['MYSQL_PASSWORD'],
                    db=app.config['MYSQL_DB'],
                    cursorclass=pymysql.cursors.DictCursor
                )
                cursor = connection.cursor()

                nuevo_folio = request.form['nuevo_folio']
                nueva_fecha = request.form['nueva_fecha']
                nuevo_origen_modelo = request.form['nuevo_origen_modelo']
                nuevo_destinatario = request.form['nuevo_destinatario']
                nuevo_chofer = request.form['nuevo_chofer']
                nuevo_no_pedido = request.form['nuevo_no_pedido']
                nuevo_folio_ida = request.form['nuevo_folio_ida']
                nuevo_placas = request.form['nuevo_placas']
                nuevo_unidad = request.form['nuevo_unidad']
                nuevo_gastos_ocupados = request.form['nuevo_gastos_ocupados']
                nuevo_gastos_depositados = request.form['nuevo_gastos_depositados']
                nuevo_diferencia = request.form['nuevo_diferencia']
                nuevo_carga_1 = request.form['nuevo_carga_1']
                nuevo_carga_2 = request.form['nuevo_carga_2']
                nuevo_carga_3 = request.form['nuevo_carga_3']
                nuevo_total_litros = request.form['nuevo_total_litros']
                nuevo_km_recorridos = request.form['nuevo_km_recorridos']

                # Actualizar los datos del viaje en la base de datos
                cursor.execute('UPDATE viajes SET folio=%s, fecha=%s, origen_modelo=%s, destinatario=%s, chofer=%s, no_pedido=%s, folio_ida=%s, placas=%s, unidad=%s, gastos_ocupados=%s, gastos_depositados=%s, diferencia=%s, carga_1=%s, carga_2=%s, carga_3=%s, total_litros=%s, km_recorridos=%s WHERE id=%s',
                               (nuevo_folio, nueva_fecha, nuevo_origen_modelo, nuevo_destinatario, nuevo_chofer, nuevo_no_pedido, nuevo_folio_ida, nuevo_placas, nuevo_unidad, nuevo_gastos_ocupados, nuevo_gastos_depositados, nuevo_diferencia, nuevo_carga_1, nuevo_carga_2, nuevo_carga_3, nuevo_total_litros, nuevo_km_recorridos, viaje_id))

                connection.commit()

                return redirect(url_for('dashboard'))

            except Exception as e:
                print(f"Error al editar el viaje: {str(e)}")
                return redirect(url_for('dashboard'))

            finally:
                if cursor:
                    cursor.close()
                if connection:
                    connection.close()
    print(request.form)
    return redirect(url_for('login'))
    


@app.route('/eliminarViaje/<int:viaje_id>')
def eliminarViaje(viaje_id):
    try:
        connection = pymysql.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            db=app.config['MYSQL_DB'],
            cursorclass=pymysql.cursors.DictCursor
        )
        cursor = connection.cursor()

        cursor.execute('DELETE FROM viajes WHERE id = %s', (viaje_id,))
        connection.commit()

        return 'Viaje eliminado correctamente.'

    except Exception as e:
        print(f"Error al eliminar el viaje: {str(e)}")
        return 'Error al eliminar el viaje.'

    finally:
        cursor.close()
        connection.close()

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
