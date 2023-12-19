import os
from os.path import join, dirname
from dotenv import load_dotenv
from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask import session
import jwt
from pymongo import MongoClient, errors
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from datetime import datetime, timedelta
from wtforms import StringField, PasswordField, TextAreaField
from wtforms.validators import InputRequired, Email, Length
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
import traceback
import hashlib
from werkzeug.utils import secure_filename
from bson import ObjectId
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity

SECRET_KEY = 'SPARTA'

app = Flask(__name__)

app.config['SECRET_KEY'] = '2f6721334df9da42e670654a7de0dffe8b70f80f5617511f' 
jwt = JWTManager(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'


TOKEN_KEY = 'mytoken'

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("DB_NAME")

client = MongoClient(MONGODB_URI)
db = client[DB_NAME]

col_konsultasi = db.riwayat_konsultasi


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_next_filename(folder_path, prefix):
    files = [f for f in os.listdir(folder_path) if f.startswith(prefix)]
    if not files:
        return f"{prefix}1"

    last_index = max([int(f[len(prefix):]) for f in files])
    return f"{prefix}{last_index + 1}"

@app.route("/")
def home():
    return render_template("index.html")

#######################################################################################################################
# Regis & login

# --------------------------- auth owner ---------------------------
# Authentication for owner
class User(UserMixin):
    def __init__(self, user_id):
        self.id = user_id

@login_manager.user_loader
def load_user(user_id):
    user_data = db.users.find_one({'_id': user_id})
    if user_data:
        user = User(user_data['_id'])  # Pass the user_id when creating the User object
        return user
    return None

def save_profilePhoto(profile_image, folder='static/foto/owner/profile/'):
    if not os.path.exists(folder):
        os.makedirs(folder)

    if profile_image:
        filename = secure_filename(profile_image.filename)
        filepath = os.path.join(folder, filename)
        profile_image.save(filepath)
        return filename
    return None

def save_buktiPhoto(bukti_pembayaran, folder='static/foto/owner/bukti_pembayaran/'):
    if not os.path.exists(folder):
        os.makedirs(folder)

    if bukti_pembayaran:
        filename = secure_filename(bukti_pembayaran.filename)
        filepath = os.path.join(folder, filename)
        bukti_pembayaran.save(filepath)
        return filename
    return None


class UserRegistrationForm(FlaskForm):
    namalengkap = StringField('Nama Lengkap', validators=[InputRequired(), Length(min=4, max=50)])
    username = StringField('Username', validators=[InputRequired(), Length(min=4, max=25)])
    nohp = StringField('No HP', validators=[InputRequired(), Length(min=10, max=15)])
    email = StringField('Email', validators=[InputRequired(), Email(), Length(max=50)])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=8, max=80)])
    alamat = TextAreaField('Alamat', validators=[InputRequired(), Length(min=10, max=200)])

class UserLoginForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired()])
    password = PasswordField('Password', validators=[InputRequired()])

@app.route("/register", methods=['GET', 'POST'])
def register():
    form = UserRegistrationForm()
    if request.method == 'POST' and form.validate_on_submit():
        try:
            data = form.data
            profile_image = request.files['profile_image']
            bukti_pembayaran = request.files['bukti_pembayaran']
            
            profile_filename = save_profilePhoto(profile_image)
            bukti_filename = save_buktiPhoto(bukti_pembayaran)
            existing_user = db.users.find_one({'username': data['username']})
            if existing_user:
                return jsonify({"result": "failure", "message": "Username already exists. Please choose a different one."})
            else:
                hashed_password = hashlib.sha256(data['password'].encode()).hexdigest()
                user_id = db.users.insert_one({
                    'namalengkap': data['namalengkap'],
                    'username': data['username'],
                    'nohp': data['nohp'],
                    'email': data['email'],
                    'password': hashed_password,
                    'alamat': data['alamat'],
                    'profile': profile_filename  ,
                    'bukti': bukti_filename  
                }).inserted_id

                user = User()
                user.id = user_id
                login_user(user)
                return redirect(url_for('login'))
        except Exception as e:
            traceback.print_exc()
            return jsonify({"result": "error", "message": str(e)})
    return render_template("register.html", form=form)

@app.route("/login", methods=['GET', 'POST'])
def login():
    form = UserLoginForm()
    if request.method == 'POST' and form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        user_data = db.users.find_one({'username': username})
        if user_data and user_data['password'] == hashlib.sha256(password.encode()).hexdigest():
            user = User(user_data['_id'])
            user.id = user_data['_id']
            login_user(user)
            return render_template("ownerDashboard.html")
        else:
            return jsonify({"result": "failure", "message": "Invalid username or password."})
    return render_template("login.html", form=form)

@app.route("/ownerDashboard")
def ownerDashboard():
    if current_user.is_authenticated:
        return render_template("ownerDashboard.html", user=current_user)
    else:
        return redirect(url_for('login'))

# --------------------------- end auth owner ---------------------------


# --------------------------- auth dokter ---------------------------
class Doctor(UserMixin):
    def __init__(self, doctor_id):
        self.id = doctor_id

@login_manager.user_loader
def load_doctor(doctor_id):
    doctor_data = db.doctors.find_one({'_id': ObjectId(doctor_id)})
    if doctor_data:
        doctor = Doctor(str(doctor_data['_id']))  # Ensure the ID matches your requirements
        return doctor
    return None

def save_photo(foto, folder='static/foto/dokter/'):
    if not os.path.exists(folder):
        os.makedirs(folder)

    if foto:
        filename = secure_filename(foto.filename)
        filepath = os.path.join(folder, filename)
        foto.save(filepath)
        return filename
    return None

class DoctorRegistrationForm(FlaskForm):
    namalengkap = StringField('Nama Lengkap', validators=[InputRequired(), Length(min=4, max=50)])
    username = StringField('Username', validators=[InputRequired(), Length(min=4, max=25)])
    nohp = StringField('No HP', validators=[InputRequired(), Length(min=10, max=15)])
    email = StringField('Email', validators=[InputRequired(), Email(), Length(max=50)])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=8, max=80)])
    alamat = TextAreaField('Alamat', validators=[InputRequired(), Length(min=10, max=200)])
    pendidikan = StringField('Pendidikan', validators=[InputRequired(), Length(min=4, max=50)])
    harga = StringField('Harga', validators=[InputRequired(), Length(min=1, max=10)])
    foto = FileField('Upload Foto', validators=[FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')])

class DoctorLoginForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired()])
    password = PasswordField('Password', validators=[InputRequired()])

@app.route("/dokterRegister", methods=['GET', 'POST'])
def dokterRegister():
    form = DoctorRegistrationForm()
    if request.method == 'POST' and form.validate_on_submit():
        try:
            data = form.data
            foto = request.files['foto']
            
            foto_filename = save_photo(foto)
            
            existing_doctor = db.doctors.find_one({'username': data['username']})
            if existing_doctor:
                return jsonify({"result": "failure", "message": "Username already exists. Please choose a different one."})
            else:
                hashed_password = hashlib.sha256(data['password'].encode()).hexdigest()
                doctor_id = db.doctors.insert_one({
                    'namalengkap': data['namalengkap'],
                    'username': data['username'],
                    'nohp': data['nohp'],
                    'email': data['email'],
                    'password': hashed_password,
                    'alamat': data['alamat'],
                    'pendidikan': data['pendidikan'],
                    'harga': data['harga'],
                    'foto': foto_filename  
                }).inserted_id

                doctor = Doctor()
                doctor.id = doctor_id
                login_user(doctor)
                return redirect(url_for('dokterLogin'))
        except Exception as e:
            traceback.print_exc()
            return jsonify({"result": "error", "message": str(e)})
    return render_template("dokterRegister.html", form=form)

@app.route("/dokterLogin", methods=['GET', 'POST'])
def dokterLogin():
    form = DoctorLoginForm()
    if request.method == 'POST' and form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        doctor_data = db.doctors.find_one({'username': username})
        if doctor_data and doctor_data['password'] == hashlib.sha256(password.encode()).hexdigest():
            doctor = Doctor(doctor_data['_id'])
            doctor.id = doctor_data['_id']
            login_user(doctor)
            return render_template("dokterDashboard.html")
        else:
            return jsonify({"result": "failure", "message": "Invalid username or password."})
    return render_template("dokterLogin.html", form=form)

@app.route("/dokterDashboard")
def dokterDashboard():
    return render_template("dokterDashboard.html", user=current_user)

@app.route("/dokterDaftar")
def dokterDaftar():
    doctors = db.doctors.find()
    return render_template("dokterDaftar.html", doctors=doctors)
# --------------------------- end auth dokter ---------------------------

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))
#######################################################################################################################
# konsultasi

doctors = []

@app.route("/daftar_dokter")
def daftar_dokter():
    doctors = db.doctors.find()
    return render_template("daftar_dokter.html", doctors=doctors)


@app.route('/detail_dokter/<string:doctor_id>')
def detail_dokter(doctor_id):
    selected_doctor = db.doctors.find_one({'_id': ObjectId(doctor_id)})
    if selected_doctor:
        ulasan_entries = db.ulasan.find({'doctor_id': ObjectId(doctor_id)}).sort("_id", -1).limit(5)
        return render_template('detail_dokter.html', doctor=selected_doctor, ulasan_entries=ulasan_entries)
    else:
        return "Dokter tidak ditemukan."

@app.context_processor
def utility_processor():
    def get_doctor_name(doctor_id):
        doctor = db.doctors.find_one({'_id': ObjectId(doctor_id)})
        if doctor:
            return doctor['namalengkap']
        return 'Dokter Tidak Ditemukan'
    
    return dict(get_doctor_name=get_doctor_name)

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    user_data = db.users.find_one({'_id': user_id})
    if user_data:
        user = User(user_data['_id']) 
        return user
    return None




@app.route('/form_konsultasi/<string:doctor_id>', methods=['GET'])
def form_konsultasi(doctor_id):
    doctor = db.doctors.find_one({'_id': ObjectId(doctor_id)})
    return render_template('form_konsultasi.html', doctor=doctor, doctor_id=doctor_id)


@app.route('/save_form_konsultasi', methods=['POST'])
def save_form_data():
    if request.method == 'POST':
        nama_kucing = request.form['namaKucing']
        jenis_kucing = request.form['jenisKucing']
        usia_kucing = request.form['usiaKucing']
        keluhan = request.form['keluhan']
        foto_keluhan = request.files['fotoKeluhan']
        bukti_pembayaran = request.files['buktiPembayaran']
        doctor_id = request.form['doctor_id']
        user_id = current_user.id if current_user.is_authenticated else None
        
        filename_keluhan = None
        filename_pembayaran = None
        
        if foto_keluhan and allowed_file(foto_keluhan.filename):
            filename_keluhan = secure_filename(foto_keluhan.filename)
            foto_keluhan.save(os.path.join(app.config['UPLOAD_FOLDER'], filename_keluhan))
        
        if bukti_pembayaran and allowed_file(bukti_pembayaran.filename):
            filename_pembayaran = secure_filename(bukti_pembayaran.filename)
            bukti_pembayaran.save(os.path.join(app.config['UPLOAD_FOLDER'], filename_pembayaran))

        result = col_konsultasi.insert_one({
            'nama_kucing': nama_kucing,
            'jenis_kucing': jenis_kucing,
            'usia_kucing': usia_kucing,
            'keluhan': keluhan,
            'foto_keluhan': filename_keluhan,  
            'bukti_pembayaran': filename_pembayaran,
            'doctor_id': ObjectId(doctor_id),
            'user_id': ObjectId(user_id)
        })

        return redirect('/riwayat')

@app.route('/riwayat')
def riwayat_konsultasi():
    riwayat_konsultasi = list(col_konsultasi.find({}))
    return render_template('riwayat_konsultasi.html', riwayat_konsultasi=riwayat_konsultasi)

#######################################################################################################################
# rekam medis

@app.route('/daftar_rekamMedis')
def daftar_rekamMedis():
    doctors = db.doctors.find()
    return render_template('daftar_rekamMedis.html', doctors=doctors)


@app.route('/detail_rekamMedis/<string:doctor_id>')
def detail_rekamMedis(doctor_id):
    selected_doctor = db.doctors.find_one({'_id': ObjectId(doctor_id)})
    if selected_doctor:
        rekam_medis = col_konsultasi.find({'doctor_id': ObjectId(doctor_id)})
        return render_template('detail_rekamMedis.html', doctor=selected_doctor, detail_rekamMedis=rekam_medis)
    else:
        return "Dokter tidak ditemukan."


#######################################################################################################################
# rekam medis view dokter
@app.route('/dokterDaftar_rmd')
def dokter_daftar_rmd():
    users = db.users.find({}, {'namalengkap': 1}) 
    consultation_data = col_konsultasi.find({}, {'nama_kucing': 1, 'jenis_kucing': 1, 'usia_kucing': 1, 'keluhan': 1, 'foto_keluhan': 1, 'bukti_pembayaran': 1, 'diagnosa': 1})

    return render_template('dokterDaftar_rmd.html', users=users, consultation_data=consultation_data)

@app.route('/tambah_diagnosa', methods=['POST'])
def tambah_diagnosa():
    if request.method == 'POST':
        konsultasi_id = request.form['konsultasi_id']
        diagnosa = request.form['diagnosa']

        result = col_konsultasi.update_one(
            {'_id': ObjectId(konsultasi_id)},
            {'$set': {'diagnosa': diagnosa}}
        )


        return jsonify({'message': 'Diagnosa berhasil ditambahkan'})

@app.route('/update_diagnosa', methods=['POST'])
def update_diagnosa():
    if request.method == 'POST':
        konsultasi_id = request.json['konsultasi_id']
        edited_diagnosa = request.json['edited_diagnosa']

        result = col_konsultasi.update_one(
            {'_id': ObjectId(konsultasi_id)},
            {'$set': {'diagnosa': edited_diagnosa}}
        )

        if result.modified_count > 0:
            col_konsultasi.update_one(
                {'konsultasi_id': ObjectId(konsultasi_id)},
                {'$set': {'diagnosa': edited_diagnosa}}
            )

            return jsonify({'message': 'Diagnosa berhasil diperbarui'})
        else:
            return jsonify({'message': 'Gagal memperbarui diagnosa'})


#########################################################################################################################################################
# Profile
    
profile_data = {
    'namalengkap': 'Nama Lengkap Pengguna',
    'email': 'contoh@contoh.com',
    'nohp': '1234567890',
    'username': 'usernamepengguna',
    'password': '*******',
    'alamat': 'Jalan Contoh No. 123, Kota Contoh, Indonesia'
}

dokter_data = {
    'namalengkap': 'Nama Lengkap Pengguna',
    'email': 'contoh@contoh.com',
    'nohp': '1234567890',
    'username': 'usernamepengguna',
    'password': '*******',
    'pendidikanterakhir': 'pendidikanterakhir',
    'lokasiklinik': 'Jalan Contoh No. 123, Kota Contoh, Indonesia'
}


@app.route('/profile_owner', methods=['GET', 'POST'])
def profile_owner():
    if request.method == 'POST':
        try:
            namalengkap = request.form['namalengkap']
            username = request.form['username']
            nohp = request.form['nohp']
            email = request.form['email']
            password = request.form['password']
            alamat = request.form['alamat']

            if not (namalengkap and username and nohp and email and password and alamat):
                return render_template('profile_owner.html', message="Please fill in all the fields.")

            hashed_password = generate_password_hash(password, method='sha256')

            profile_data = {
                'namalengkap': namalengkap,
                'username': username,
                'nohp': nohp,
                'email': email,
                'password': hashed_password,
                'alamat': alamat,
            }

            inserted_profile = db.profile.insert_one(profile_data)

            if inserted_profile.inserted_id:
                return render_template('profile_owner.html', message="Profile data saved successfully!")
            else:
                return render_template('profile_owner.html', message="Failed to save profile data. Please try again.")
        except Exception as e:
            return render_template('profile_owner.html', message=f"An error occurred: {str(e)}")
    else:
        return render_template('profile_owner.html', profile_data={})
    

@app.route('/profile_dokter', methods=['GET', 'POST'])
def profile_dokter():
    if request.method == 'POST':
        try:
            namalengkap = request.form['namalengkap']
            username = request.form['username']
            nohp = request.form['nohp']
            email = request.form['email']
            password = request.form['password']
            pendidikanterakhir = request.form['pendidikanterakhir']
            lokasiklinik = request.form['lokasiklinik']

            if not (namalengkap and username and nohp and email and password and pendidikanterakhir and lokasiklinik):
                return render_template('profile_dokter.html', message="Please fill in all the fields.")

            hashed_password = generate_password_hash(password, method='sha256')

            dokter_data = {
                'namalengkap': namalengkap,
                'username': username,
                'nohp': nohp,
                'email': email,
                'password': hashed_password,
                'pendidikanterakhir': pendidikanterakhir,
                'lokasiklinik': lokasiklinik,
            }


            inserted_dokter = db.dokter.insert_one(dokter_data)

            if inserted_dokter.inserted_id:
                return render_template('profile_dokter.html', message="Profile data saved successfully!")
            else:
                return render_template('profile_dokter.html', message="Failed to save profile data. Please try again.")
        except Exception as e:
            return render_template('profile_dokter.html', message=f"An error occurred: {str(e)}")
    else:
        return render_template('profile_dokter.html')
    
 
@app.route('/edit_profile_owner', methods=['POST'])
def edit_profile():
    namalengkap = request.form.get('namalengkap')
    email = request.form.get('email')
    nohp = request.form.get('nohp')
    username = request.form.get('username')
    password = request.form.get('password')
    alamatlengkap = request.form.get('alamatlengkap')

    if not (namalengkap and email and nohp and username and password and alamatlengkap):
        return jsonify(result='error', message='Please fill in all the required fields.')

    hashed_password = generate_password_hash(password, method='sha256')

    updated_data = {
        'namalengkap': namalengkap,
        'email': email,
        'nohp': nohp,
        'username': username,
        'password': hashed_password,
        'alamatlengkap': alamatlengkap,
    }

    return jsonify(result='success', **updated_data)


@app.route('/edit_profile_dokter', methods=['POST'])
def edit_profile_dokter():
    namalengkap = request.form.get('namalengkap')
    email = request.form.get('email')
    nohp = request.form.get('nohp')
    username = request.form.get('username')
    password = request.form.get('password')
    pendidikanterakhir = request.form.get('pendidikanterakhir')
    lokasiklinik = request.form.get('lokasiklinik')
    if not (namalengkap and username and nohp and email and password and pendidikanterakhir and lokasiklinik):
             return render_template('profile_owner.html', message="Please fill in all the fields.")

    hashed_password = generate_password_hash(password, method='sha256')


    update_data = {
    'namalengkap': namalengkap,
    'email': email,
    'nohp': nohp,
    'username': username,
    'pendidikanterakhir': pendidikanterakhir,
    'lokasiklinik': lokasiklinik,
}

    return jsonify(result='success', **update_data)


#########################################################################################################################################################
# Ulasan
col_ulasan = db.ulasan
ulasan_dokter = [] 

@app.route('/get_doctor_name/<string:doctor_id>', methods=['GET'])
def get_doctor_name(doctor_id):
    doctor = db.doctors.find_one({'_id': ObjectId(doctor_id)})
    if doctor:
        return doctor['namalengkap']
    return 'Dokter Tidak Ditemukan'


@app.route('/daftar_ulasan')
def daftar():
    doctors = db.doctors.find()
    return render_template("daftar_ulasan.html", doctors=doctors)


@app.route('/form_ulasan/<string:doctor_id>', methods=['GET'])
def show_form_ulasan(doctor_id):
    doctor = db.doctors.find_one({'_id': ObjectId(doctor_id)})
    if doctor:
        ulasan_entries = db.ulasan.find({'doctor_id': ObjectId(doctor_id)}).sort("_id", -1).limit(5)
        return render_template('form_ulasan.html', ulasan_entries=ulasan_entries, doctor_id=doctor_id, doctor=doctor)
    else:
        return 'Dokter Tidak Ditemukan'

@app.route('/submit_form_ulasan/<string:doctor_id>', methods=['POST'])
def submit_form_ulasan(doctor_id):
    ulasan_text = request.form.get('ulasan')
    rating = request.form.get('rating')

    doc = {
        'ulasan': ulasan_text,
        'rating': rating,
        'doctor_id': ObjectId(doctor_id)
    }
    db.ulasan.insert_one(doc)

    return redirect(url_for('show_specific_reviews', doctor_id=doctor_id))


@app.route('/reviews/<string:doctor_id>')
def show_specific_reviews(doctor_id):
    ulasan_entries = db.ulasan.find({'doctor_id': ObjectId(doctor_id)}).sort("_id", -1).limit(15)
    
    return render_template('halaman_ulasan.html', ulasan_entries=ulasan_entries, doctor_id=doctor_id)


@app.route('/delete_review/<string:review_id>/<string:doctor_id>', methods=['POST'])
def delete_review(review_id, doctor_id):
    db.ulasan.delete_one({'_id': ObjectId(review_id)})

    return redirect(url_for('show_specific_reviews', doctor_id=doctor_id))

@app.route('/view_doctor_reviews/<string:doctor_id>')
def view_doctor_reviews(doctor_id):
    if current_user.is_authenticated and current_user.id == doctor_id:
        doctor = db.doctors.find_one({'_id': ObjectId(doctor_id)})
        if doctor:
            ulasan_entries = db.ulasan.find({'doctor_id': ObjectId(doctor_id)}).sort("_id", -1)
            return render_template('halaman_ulasan_dokter.html', ulasan_entries=ulasan_entries, doctor=doctor)
        else:
            return 'Dokter Tidak Ditemukan.'
    else:
        return 'Anda tidak memiliki izin untuk melihat ulasan.'



if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
