import os
from os.path import join, dirname
from dotenv import load_dotenv
from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_login import logout_user
import jwt
from pymongo import MongoClient, errors
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from datetime import datetime
from wtforms import StringField, PasswordField, TextAreaField
from wtforms.validators import InputRequired, Email, Length
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
import traceback
import hashlib
from werkzeug.utils import secure_filename
from bson import ObjectId

SECRET_KEY = 'SPARTA'

app = Flask(__name__)

app.config['SECRET_KEY'] = '2f6721334df9da42e670654a7de0dffe8b70f80f5617511f' 

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

###############################################################################################
# Regis & login

# --------------------------- auth owner ---------------------------
class User(UserMixin):
    pass

@login_manager.user_loader
def load_user(user_id):
    user_data = db.users.find_one({'_id': user_id})
    if user_data:
        user = User()
        user.id = user_data['_id']
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
            user = User()
            user.id = user_data['_id']
            login_user(user)
            return render_template("ownerDashboard.html")
        else:
            return jsonify({"result": "failure", "message": "Invalid username or password."})
    return render_template("login.html", form=form)

@app.route("/ownerDashboard")
@login_required
def ownerDashboard():
    return render_template("ownerDashboard.html", user=current_user)
# --------------------------- end auth owner ---------------------------


# --------------------------- auth dokter ---------------------------
class Doctor(UserMixin):
    pass

@login_manager.user_loader
def load_doctor(doctor_id):
    doctor_data = db.doctors.find_one({'_id': doctor_id})
    if doctor_data:
        doctor = Doctor()
        doctor.id = doctor_data['_id']
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
            doctor = Doctor()
            doctor.id = doctor_data['_id']
            login_user(doctor)
            return render_template("dokterDashboard.html")
        else:
            return jsonify({"result": "failure", "message": "Invalid username or password."})
    return render_template("dokterLogin.html", form=form)

@app.route("/dokterDashboard")
@login_required
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

#########################################################################################################################################################
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
        return render_template('detail_dokter.html', doctor=selected_doctor)
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





@app.route('/form_konsultasi/<string:doctor_id>', methods=['GET'])
def form_konsultasi(doctor_id):
    doctor = db.doctors.find_one({'_id': ObjectId(doctor_id)})
    return render_template('form_konsultasi.html', doctor=doctor, doctor_id=doctor_id)


@app.route('/save_form_konsultasi', methods=['POST'])
def save_form_data():
    if request.method == 'POST':
        nama_pemilik = request.form['namaPemilik']
        nama_kucing = request.form['namaKucing']
        jenis_kucing = request.form['jenisKucing']
        usia_kucing = request.form['usiaKucing']
        keluhan = request.form['keluhan']
        foto_keluhan = request.files['fotoKeluhan']
        bukti_pembayaran = request.files['buktiPembayaran']
        doctor_id = request.form['doctor_id'] 
        
        filename_keluhan = None
        filename_pembayaran = None
        
        if foto_keluhan and allowed_file(foto_keluhan.filename):
            filename_keluhan = secure_filename(foto_keluhan.filename)
            foto_keluhan.save(os.path.join(app.config['UPLOAD_FOLDER'], filename_keluhan))
        
        if bukti_pembayaran and allowed_file(bukti_pembayaran.filename):
            filename_pembayaran = secure_filename(bukti_pembayaran.filename)
            bukti_pembayaran.save(os.path.join(app.config['UPLOAD_FOLDER'], filename_pembayaran))

        result = col_konsultasi.insert_one({
            'nama_pemilik': nama_pemilik,
            'nama_kucing': nama_kucing,
            'jenis_kucing': jenis_kucing,
            'usia_kucing': usia_kucing,
            'keluhan': keluhan,
            'foto_keluhan': filename_keluhan,  
            'bukti_pembayaran': filename_pembayaran,
           'doctor_id': ObjectId(doctor_id)
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

    
# rekam medis view dokter
@app.route('/dokterDaftar_rmd')
def dokterDaftar_rmd():
    return render_template('dokterDaftar_rmd.html')

@app.route('/dokterDetail_rmd') 
def dokterDetail_rmd():
    return render_template('dokterDetail_rmd.html')


#########################################################################################################################################################
# Profile

@app.route('/profile')
def profile():
    return render_template('profile_owner.html')

@app.route('/profile_dokter')
def dokter():
    return render_template('profile_dokter.html')

@app.route("/update_profile", methods=["POST"])
def save_img():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=["HS256"])
        username = payload["id"]
        name_receive = request.form["name_give"]
        about_receive = request.form["about_give"]

        new_doc = {
            "profile_name": name_receive, 
            "profile_info": about_receive
        }
        if "file_give" in request.files:
            file = request.files["file_give"]
            filename = secure_filename(file.filename)
            extension = filename.split(".")[-1]
            file_path = f"profile_pics/{username}.{extension}"
            file.save("./static/" + file_path)
            new_doc["profile_pic"] = filename
            new_doc["profile_pic_real"] = file_path

        db.profile.update_one(
            {"username": payload["id"]}, 
            
            {"$set": new_doc}
        )
        return jsonify({"result": "success", "msg": "Profile updated!"})
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for("home"))
    

# Ulasan
collection = db['ulasan']
ulasan_dokter = [] 


@app.route('/daftar_ulasan')
def daftar():
    return render_template('daftar_ulasan.html')

@app.route('/form_ulasan', methods=['GET'])
def show_form():

    ulasan_entries = db.ulasan.find().sort("_id", -1).limit(5)

    return render_template('form_ulasan.html', ulasan_entries=ulasan_entries)

@app.route('/form_ulasan', methods=['POST'])
def submit_form():
    ulasan_text = request.form.get('ulasan')
    rating = request.form.get('rating')

    doc = {
        'ulasan': ulasan_text,
        'rating': rating
    }
    db.ulasan.insert_one(doc)

    return redirect(url_for('ulasan'))

@app.route('/halaman_ulasan', methods=['GET'])
def ulasan():
    ulasan_entries = db.ulasan.find().sort("_id", -1).limit(15)

    return render_template('halaman_ulasan.html', ulasan_entries=ulasan_entries)

@app.route('/hapus/<string:review_id>', methods=['POST'])
def hapus_review(review_id):
    try:
        result = collection.delete_one({"_id": ObjectId(review_id)})

        if result.deleted_count > 0:
            return jsonify({"message": "Ulasan berhasil dihapus."})
        else:
            return jsonify({"message": "Ulasan tidak ditemukan."})

    except Exception as e:
        return jsonify({"message": str(e)})




if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
