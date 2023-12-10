import os
from os.path import join, dirname
from dotenv import load_dotenv

from flask import Flask, render_template, request, url_for, redirect, jsonify
import jwt
from pymongo import MongoClient
from werkzeug.utils import secure_filename
from bson import ObjectId

SECRET_KEY = 'SPARTA'

app = Flask(__name__)

TOKEN_KEY = 'mytoken'

ulasan_dokter = [] 


UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("DB_NAME")

client = MongoClient(MONGODB_URI)
db = client[DB_NAME]

col_konsultasi = db.riwayat_konsultasi
col_user = db.owner
col_dokter = db.dokter

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_next_filename(folder_path, prefix):
    files = [f for f in os.listdir(folder_path) if f.startswith(prefix)]
    if not files:
        return f"{prefix}1"

    last_index = max([int(f[len(prefix):]) for f in files])
    return f"{prefix}{last_index + 1}"


# GET
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/docter")
def docter():
    return render_template("dokter_login.html")

@app.route("/register")
def register():
    return render_template("register.html")

@app.route("/regisdocter")
def regisdocter():
    return render_template("dokter_register.html")


@app.route('/form_konsultasi')
def form_konsultasi():
    return render_template('form_konsultasi.html')

@app.route('/riwayat')
def riwayat_konsultasi():
    riwayat_konsultasi = list(col_konsultasi.find({}))
    return render_template('riwayat_konsultasi.html', riwayat_konsultasi=riwayat_konsultasi)

@app.route('/daftar_rekam_medis')
def daftar_rekam_medis():
    return render_template('rekam_medis.html')

@app.route('/detail_rekam_medis/<doctor_id>')
def detail_rekam_medis(doctor_id):
    doctor_info = col_konsultasi.find_one({'_id': ObjectId(doctor_id)})

    return render_template('detail_rekamMedis.html', doctor_info=doctor_info)

@app.route('/dokter_rmd')
def dokter_rekam_medis():
    return render_template('dokter_rmd.html')


@app.route('/profile')
def profile():
    return render_template('profile_owner.html')

@app.route('/profile_dokter')
def dokter():
    return render_template('dokter_profile.html')

@app.route('/detail_rmd')
def detail():
    return render_template('dokter_detail_rmd.html')

@app.route('/form_ulasan')
def form1():
    return render_template('form_ulasan.html')

@app.route('/daftar_ulasan')
def daftar_ulasan():
    return render_template('daftar_ulasan.html')

@app.route('/halaman_ulasan')
def halaman():
    return render_template('halaman_ulasan.html')


# POST

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
            'bukti_pembayaran': filename_pembayaran  
        })

        return redirect('/riwayat')



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

        db.users.update_one(
            {"username": payload["id"]}, 
            {"$set": new_doc}
        )
        return jsonify({"result": "success", "msg": "Profile updated!"})
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for("home"))

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
