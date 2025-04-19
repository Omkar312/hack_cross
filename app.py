import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, render_template, request, redirect, url_for, flash
import secrets
from datetime import datetime, timedelta
import random

# Initialize Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'

def calculate_period_number():
    utc_now = datetime.utcnow()
    total_minutes = utc_now.hour * 60 + utc_now.minute
    return f"{utc_now.strftime('%Y%m%d')}1000{10001 + total_minutes}"

def generate_prediction(period, old_chart):
    random.seed(period)
    last = old_chart[-7:] if len(old_chart) >= 7 else old_chart
    trend_score = {'BIG': 0, 'SMALL': 0}
    for res in last:
        trend_score[res] += 1

    if last[-3:] == ['BIG'] * 3:
        return 'SMALL'
    elif last[-3:] == ['SMALL'] * 3:
        return 'BIG'
    elif last[-4:] in (['BIG', 'SMALL', 'BIG', 'SMALL'], ['SMALL', 'BIG', 'SMALL', 'BIG']):
        return last[-1]

    return 'SMALL' if trend_score['BIG'] > trend_score['SMALL'] else 'BIG'

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/validate_key', methods=['POST'])
def validate_key():
    user_key = request.form.get('key')
    key_query = db.collection('user_keys').where("key", "==", user_key).stream()

    for record in key_query:
        key_data = record.to_dict()
        if key_data["is_permanent"]:
            return redirect(url_for('predict'))
        elif key_data["expiration_time"] and datetime.utcnow() > key_data["expiration_time"]:
            flash("Key expired!", "danger")
            return redirect(url_for('login'))
        else:
            return redirect(url_for('predict'))

    flash("Invalid key!", "danger")
    return redirect(url_for('login'))

@app.route('/predict')
def predict():
    period = calculate_period_number()
    old_chart = ['BIG', 'SMALL', 'BIG', 'SMALL', 'BIG', 'BIG', 'SMALL']
    prediction = generate_prediction(period, old_chart)
    return render_template('predict.html', period=period, prediction=prediction)

@app.route('/generate_key', methods=['GET', 'POST'])
def generate_key():
    if request.method == 'POST':
        is_permanent = request.form.get('is_permanent') == 'on'
        expiration_time = None
        if not is_permanent:
            expiry_minutes = int(request.form.get('expiry_duration'))
            expiration_time = datetime.utcnow() + timedelta(minutes=expiry_minutes)
        key = secrets.token_hex(16)
        db.collection('user_keys').add({
            'key': key,
            'is_permanent': is_permanent,
            'expiration_time': expiration_time
        })
        flash(f"Key generated: {key}", "success")
        return redirect(url_for('generate_key'))
    return render_template('generate_key.html')

@app.route('/admin_dashboard')
def dashboard():
    key_stream = db.collection('user_keys').stream()
    keys = [k.to_dict() for k in key_stream]
    return render_template('admin_dashboard.html', keys=keys)

if __name__ == "__main__":
    app.run(debug=True)
