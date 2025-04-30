from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, EmailField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import pickle
import os
from fpdf import FPDF
import matplotlib
matplotlib.use('Agg')  # Use Agg backend for non-GUI rendering
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64
from datetime import datetime
import logging
import tempfile

# Set up logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-secure123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///rainfall.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_TYPE'] = 'filesystem'
# app.config['FORCE_HTTPS'] = True  # Uncomment in production
Session(app)
db = SQLAlchemy(app)

# Load the model
try:
    with open('model/rainfall_prediction_model.pkl', 'rb') as file:
        model_data = pickle.load(file)
    model = model_data['model']
    feature_names = model_data['feature_names']
except FileNotFoundError:
    print("Error: rainfall_prediction_model.pkl not found in model/ directory")
    exit(1)
except Exception as e:
    print(f"Error loading model: {e}")
    exit(1)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

class Prediction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    pressure = db.Column(db.Float, nullable=False)
    dewpoint = db.Column(db.Float, nullable=False)
    humidity = db.Column(db.Float, nullable=False)
    cloud = db.Column(db.Float, nullable=False)
    sunshine = db.Column(db.Float, nullable=False)
    windspeed = db.Column(db.Float, nullable=False)
    result = db.Column(db.String(20), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Forms
class LoginForm(FlaskForm):
    identifier = StringField('Username or Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=80)])
    full_name = StringField('Full Name', validators=[DataRequired()])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

# Create database
with app.app_context():
    try:
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                full_name='Admin User',
                email='admin@example.com',
                password=generate_password_hash('admin123', method='pbkdf2:sha256')
            )
            db.session.add(admin)
            db.session.commit()
    except Exception as e:
        print(f"Error creating database: {e}")
        exit(1)

# PDF Generation
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'RainCast AI Admin Insights Report', 0, 1, 'C')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, title, 0, 1, 'L')
        self.ln(5)

    def chapter_body(self, body):
        self.set_font('Arial', '', 12)
        self.multi_cell(0, 10, body)
        self.ln()

    def add_image_from_base64(self, base64_data, x, y, w, h):
        img_data = base64.b64decode(base64_data)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
            tmp_file.write(img_data)
            tmp_file_path = tmp_file.name
        try:
            self.image(tmp_file_path, x, y, w, h)
        finally:
            os.unlink(tmp_file_path)

# Login required decorator
def login_required(f):
    def wrap(*args, **kwargs):
        logging.debug(f"Checking session: user_id in session: {'user_id' in session}")
        if 'user_id' not in session:
            flash('Please login first!', 'danger')
            logging.debug("Redirecting to login due to missing session")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

# Cache control decorator
def no_cache(f):
    def decorated_function(*args, **kwargs):
        response = make_response(f(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
        return response
    decorated_function.__name__ = f.__name__
    return decorated_function

# Routes
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    logging.debug(f"Form submitted: {request.method == 'POST'}, Form valid: {form.validate_on_submit()}")
    if form.validate_on_submit():
        identifier = form.identifier.data
        password = form.password.data
        user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()
        logging.debug(f"User found: {user}, Password match: {user and check_password_hash(user.password, password) if user else False}")
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            flash('Login successful!', 'success')
            logging.debug("Redirecting to home")
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials!', 'danger')
            logging.debug("Invalid credentials")
    else:
        logging.debug(f"Form errors: {form.errors}")
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first() or User.query.filter_by(email=form.email.data).first():
            flash('Username or email already exists!', 'danger')
            return redirect(url_for('register'))
        user = User(
            username=form.username.data,
            full_name=form.full_name.data,
            email=form.email.data,
            password=generate_password_hash(form.password.data, method='pbkdf2:sha256')
        )
        db.session.add(user)
        db.session.commit()
        flash('Account created successfully! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/logout')
@no_cache
def logout():
    session.pop('user_id', None)
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))

@app.route('/home')
@login_required
@no_cache
def home():
    return render_template('home.html')

@app.route('/about')
@login_required
@no_cache
def about():
    return render_template('about.html')

@app.route('/contact')
@login_required
@no_cache
def contact():
    return render_template('contact.html')

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    form = LoginForm()
    if form.validate_on_submit():
        identifier = form.identifier.data
        password = form.password.data
        user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()
        if user and check_password_hash(user.password, password) and user.username == 'admin':
            session['user_id'] = user.id
            flash('Admin login successful!', 'success')
            return redirect(url_for('admin'))
        else:
            flash('Invalid admin credentials!', 'danger')
    return render_template('admin_login.html', form=form)

@app.route('/predict', methods=['GET', 'POST'])
@login_required
@no_cache
def predict():
    if request.method == 'POST':
        try:
            input_data = (
                float(request.form['pressure']),
                float(request.form['dewpoint']),
                float(request.form['humidity']),
                float(request.form['cloud']),
                float(request.form['sunshine']),
                float(request.form['windspeed'])
            )
            input_df = pd.DataFrame([input_data], columns=feature_names)
            prediction = model.predict(input_df)[0]
            result = 'Rainfall' if prediction == 1 else 'No Rainfall'

            # Save prediction to database
            prediction_entry = Prediction(
                user_id=session['user_id'],
                pressure=input_data[0],
                dewpoint=input_data[1],
                humidity=input_data[2],
                cloud=input_data[3],
                sunshine=input_data[4],
                windspeed=input_data[5],
                result=result
            )
            db.session.add(prediction_entry)
            db.session.commit()

            # Generate PDF
            pdf = PDF()
            pdf.add_page()
            pdf.chapter_title('Input Parameters')
            pdf.chapter_body(
                f"Pressure: {input_data[0]} hPa\n"
                f"Dewpoint: {input_data[1]} °C\n"
                f"Humidity: {input_data[2]} %\n"
                f"Cloud Cover: {input_data[3]} %\n"
                f"Sunshine: {input_data[4]} hours\n"
                f"Windspeed: {input_data[5]} km/h"
            )
            pdf.chapter_title('Prediction Result')
            pdf.chapter_body(result)
            pdf_file = f'static/downloads/prediction_{prediction_entry.id}.pdf'
            pdf.output(pdf_file)

            return render_template('predict.html', prediction=result, pdf_file=pdf_file)
        except ValueError:
            flash('Please enter valid numeric values!', 'danger')
    return render_template('predict.html')

@app.route('/admin')
@login_required
@no_cache
def admin():
    if db.session.get(User, session['user_id']).username != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('home'))
    predictions = Prediction.query.order_by(Prediction.timestamp.desc()).limit(10).all()
    total_predictions = Prediction.query.count()
    unique_users = db.session.query(Prediction.user_id).distinct().count()
    # Calculate averages with fallback for None
    avg_query = db.session.query(
        db.func.avg(Prediction.pressure),
        db.func.avg(Prediction.dewpoint),
        db.func.avg(Prediction.humidity),
        db.func.avg(Prediction.cloud),
        db.func.avg(Prediction.sunshine),
        db.func.avg(Prediction.windspeed)
    ).first()
    logging.debug(f"Raw avg_inputs query result: {avg_query}")
    avg_inputs = tuple(0.0 if v is None else v for v in avg_query) if avg_query else (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    # Visualizations
    plot_url1, plot_url2, plot_url3 = None, None, None
    try:
        data = pd.read_csv('Rainfall.csv')
        logging.debug(f"Columns in Rainfall.csv: {data.columns.tolist()}")
        # Clean column names (strip spaces) and select expected columns
        data.columns = data.columns.str.strip()
        expected_columns = ['pressure', 'dewpoint', 'humidity', 'cloud', 'sunshine', 'windspeed', 'rainfall']
        available_columns = [col for col in expected_columns if col in data.columns]
        if len(available_columns) != len(expected_columns):
            flash(f'Invalid columns in Rainfall.csv! Expected: {expected_columns}. Found: {data.columns.tolist()}', 'danger')
            # Fallback with sample data
            data = pd.DataFrame({
                'pressure': [1013.0, 1012.0],
                'dewpoint': [15.0, 14.5],
                'humidity': [60.0, 65.0],
                'cloud': [50.0, 55.0],
                'sunshine': [5.0, 4.5],
                'windspeed': [10.0, 12.0],
                'rainfall': [1, 0]
            })
        else:
            data = data[expected_columns]  # Select only expected columns
            # Rainfall Distribution
            plt.figure(figsize=(6, 4))
            sns.countplot(x='rainfall', data=data)
            plt.title('Rainfall Distribution')
            img1 = io.BytesIO()
            plt.savefig(img1, format='png')
            img1.seek(0)
            plot_url1 = base64.b64encode(img1.getvalue()).decode()
            plt.close()

            # Humidity vs Rainfall
            plt.figure(figsize=(6, 4))
            sns.scatterplot(x='humidity', y='rainfall', data=data)
            plt.title('Humidity vs Rainfall')
            img2 = io.BytesIO()
            plt.savefig(img2, format='png')
            img2.seek(0)
            plot_url2 = base64.b64encode(img2.getvalue()).decode()
            plt.close()
    except FileNotFoundError:
        flash('Rainfall.csv not found!', 'danger')
        # Fallback with sample data
        data = pd.DataFrame({
            'pressure': [1013.0, 1012.0],
            'dewpoint': [15.0, 14.5],
            'humidity': [60.0, 65.0],
            'cloud': [50.0, 55.0],
            'sunshine': [5.0, 4.5],
            'windspeed': [10.0, 12.0],
            'rainfall': [1, 0]
        })

    # Prediction Trend
    try:
        pred_data = pd.read_sql_query(db.session.query(Prediction).statement, db.engine)
        logging.debug(f"Prediction data: {pred_data}")
        if not pred_data.empty:
            pred_data['timestamp'] = pd.to_datetime(pred_data['timestamp'])
            pred_data['date'] = pred_data['timestamp'].dt.date
            trend = pred_data.groupby('date').size()
            logging.debug(f"Trend data: {trend}")
            if len(trend) >= 1:
                plt.figure(figsize=(6, 4))
                trend.plot(kind='line', marker='o')
                plt.title('Prediction Trend Over Time')
                plt.xlabel('Date')
                plt.ylabel('Number of Predictions')
                plt.xticks(rotation=45)
                plt.tight_layout()
                img3 = io.BytesIO()
                plt.savefig(img3, format='png', bbox_inches='tight')
                img3.seek(0)
                plot_url3 = base64.b64encode(img3.getvalue()).decode()
                plt.close()
            else:
                logging.debug("Not enough data points to plot trend.")
        else:
            logging.debug("No prediction data available.")
    except Exception as e:
        logging.error(f"Error generating prediction trend: {e}")
        flash('Error generating prediction trend.', 'danger')

    return render_template('admin.html', 
                         predictions=predictions, 
                         total_predictions=total_predictions,
                         unique_users=unique_users,
                         avg_inputs=avg_inputs,
                         plot_url1=plot_url1,
                         plot_url2=plot_url2,
                         plot_url3=plot_url3)

@app.route('/download/<path:filename>')
@login_required
@no_cache
def download_file(filename):
    return send_file(filename, as_attachment=True)

@app.route('/download_insights')
@login_required
@no_cache
def download_insights():
    if db.session.get(User, session['user_id']).username != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('home'))

    # Fetch recent predictions
    predictions = Prediction.query.order_by(Prediction.timestamp.desc()).limit(10).all()
    
    # Recalculate statistics
    total_predictions = Prediction.query.count()
    unique_users = db.session.query(Prediction.user_id).distinct().count()
    avg_query = db.session.query(
        db.func.avg(Prediction.pressure),
        db.func.avg(Prediction.dewpoint),
        db.func.avg(Prediction.humidity),
        db.func.avg(Prediction.cloud),
        db.func.avg(Prediction.sunshine),
        db.func.avg(Prediction.windspeed)
    ).first()
    avg_inputs = tuple(0.0 if v is None else v for v in avg_query) if avg_query else (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    # Recalculate visualizations
    plot_url1, plot_url2, plot_url3 = None, None, None
    try:
        data = pd.read_csv('Rainfall.csv')
        data.columns = data.columns.str.strip()
        expected_columns = ['pressure', 'dewpoint', 'humidity', 'cloud', 'sunshine', 'windspeed', 'rainfall']
        available_columns = [col for col in expected_columns if col in data.columns]
        if len(available_columns) != len(expected_columns):
            data = pd.DataFrame({
                'pressure': [1013.0, 1012.0],
                'dewpoint': [15.0, 14.5],
                'humidity': [60.0, 65.0],
                'cloud': [50.0, 55.0],
                'sunshine': [5.0, 4.5],
                'windspeed': [10.0, 12.0],
                'rainfall': [1, 0]
            })
        else:
            data = data[expected_columns]
            plt.figure(figsize=(6, 4))
            sns.countplot(x='rainfall', data=data)
            plt.title('Rainfall Distribution')
            img1 = io.BytesIO()
            plt.savefig(img1, format='png')
            img1.seek(0)
            plot_url1 = base64.b64encode(img1.getvalue()).decode()
            plt.close()

            plt.figure(figsize=(6, 4))
            sns.scatterplot(x='humidity', y='rainfall', data=data)
            plt.title('Humidity vs Rainfall')
            img2 = io.BytesIO()
            plt.savefig(img2, format='png')
            img2.seek(0)
            plot_url2 = base64.b64encode(img2.getvalue()).decode()
            plt.close()
    except FileNotFoundError:
        data = pd.DataFrame({
            'pressure': [1013.0, 1012.0],
            'dewpoint': [15.0, 14.5],
            'humidity': [60.0, 65.0],
            'cloud': [50.0, 55.0],
            'sunshine': [5.0, 4.5],
            'windspeed': [10.0, 12.0],
            'rainfall': [1, 0]
        })

    try:
        pred_data = pd.read_sql_query(db.session.query(Prediction).statement, db.engine)
        if not pred_data.empty:
            pred_data['timestamp'] = pd.to_datetime(pred_data['timestamp'])
            pred_data['date'] = pred_data['timestamp'].dt.date
            trend = pred_data.groupby('date').size()
            if len(trend) >= 1:
                plt.figure(figsize=(6, 4))
                trend.plot(kind='line', marker='o')
                plt.title('Prediction Trend Over Time')
                plt.xlabel('Date')
                plt.ylabel('Number of Predictions')
                plt.xticks(rotation=45)
                plt.tight_layout()
                img3 = io.BytesIO()
                plt.savefig(img3, format='png', bbox_inches='tight')
                img3.seek(0)
                plot_url3 = base64.b64encode(img3.getvalue()).decode()
                plt.close()
    except Exception as e:
        logging.error(f"Error generating prediction trend: {e}")

    # Generate PDF
    pdf = PDF()
    pdf.add_page()
    
    # Add Recent Predictions
    pdf.chapter_title('Recent Predictions')
    if predictions:
        header = "User ID | Pressure (hPa) | Dewpoint (°C) | Humidity (%) | Cloud Cover (%) | Sunshine (hours) | Windspeed (km/h) | Result | Timestamp"
        pdf.chapter_body(header)
        pdf.chapter_body("-" * 100)
        for pred in predictions:
            row = (
                f"{pred.user_id} | "
                f"{round(pred.pressure, 2)} | "
                f"{round(pred.dewpoint, 2)} | "
                f"{round(pred.humidity, 2)} | "
                f"{round(pred.cloud, 2)} | "
                f"{round(pred.sunshine, 2)} | "
                f"{round(pred.windspeed, 2)} | "
                f"{pred.result} | "
                f"{pred.timestamp}"
            )
            pdf.chapter_body(row)
    else:
        pdf.chapter_body("No recent predictions available.")
    pdf.ln(10)

    # Add Statistics
    pdf.chapter_title('Prediction Statistics')
    pdf.chapter_body(f"Total Predictions: {total_predictions}\n")
    pdf.chapter_body(f"Unique Users: {unique_users}\n")
    pdf.chapter_body("Average Inputs:\n")
    pdf.chapter_body(
        f"Pressure: {round(avg_inputs[0] if avg_inputs[0] is not None else 0.0, 2)} hPa\n"
        f"Dewpoint: {round(avg_inputs[1] if avg_inputs[1] is not None else 0.0, 2)} °C\n"
        f"Humidity: {round(avg_inputs[2] if avg_inputs[2] is not None else 0.0, 2)} %\n"
        f"Cloud Cover: {round(avg_inputs[3] if avg_inputs[3] is not None else 0.0, 2)} %\n"
        f"Sunshine: {round(avg_inputs[4] if avg_inputs[4] is not None else 0.0, 2)} hours\n"
        f"Windspeed: {round(avg_inputs[5] if avg_inputs[5] is not None else 0.0, 2)} km/h\n"
    )
    pdf.ln(10)

    # Add Visualizations
    if plot_url1:
        pdf.chapter_title('Rainfall Distribution')
        pdf.add_image_from_base64(plot_url1, 10, pdf.get_y(), 190, 80)
        pdf.ln(85)
    if plot_url2:
        pdf.chapter_title('Humidity vs Rainfall')
        pdf.add_image_from_base64(plot_url2, 10, pdf.get_y(), 190, 80)
        pdf.ln(85)
    if plot_url3:
        pdf.chapter_title('Prediction Trend Over Time')
        pdf.add_image_from_base64(plot_url3, 10, pdf.get_y(), 190, 80)
        pdf.ln(85)
    else:
        pdf.chapter_body('No prediction trend data available.')
        pdf.ln(10)

    # Save PDF
    pdf_file = f'static/downloads/insights_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    pdf.output(pdf_file)
    return send_file(pdf_file, as_attachment=True, download_name='admin_insights.pdf')

if __name__ == '__main__':
    app.run(debug=True)