import RPi.GPIO as GPIO
from datetime import datetime, timedelta
from flask import Flask, flash, request, render_template, jsonify, redirect, url_for
import json
import os
import time 
import secrets
from traceback import format_exc

app = Flask(__name__)
secret_key = secrets.token_hex(16)
app.secret_key = secret_key

GPIO.setmode(GPIO.BCM)

# Configuration
LIGHT_PIN = 17  # GPIO pin connected to the relay module
BUFFER_TIME = 10  # Buffer time in seconds

# Simulated user roles (admin and user)
users = {
    'admin': {
        'username': 'admin',
        'role': 'admin',
        'password': 'admin',
    },
    'user': {
        'username': 'user',
        'role': 'user',
        'password': '123',
    },
}

# Global variables
current_user = None
time_on = None
time_off = None

# Load the last set times from a JSON file
try:
    with open('last_set_times.json', 'r') as file:
        last_set_times = json.load(file)
        time_on = last_set_times['time_on']
        time_off = last_set_times['time_off']
except (FileNotFoundError, json.JSONDecodeError):
    last_set_times = {'time_on': None, 'time_off': None}

# Helper functions
def save_last_set_times():
    with open('last_set_times.json', 'w') as file:
        json.dump(last_set_times, file)

def setup():
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(LIGHT_PIN, GPIO.OUT)
    GPIO.output(LIGHT_PIN, GPIO.LOW)

def turn_on_light():
    print("Turning the light ON")
    GPIO.output(LIGHT_PIN, GPIO.HIGH)

def turn_off_light():
    print("Turning the light OFF")
    GPIO.output(LIGHT_PIN, GPIO.LOW)

def is_authenticated():
    return current_user is not None

def is_admin():
    return current_user and current_user['role'] == 'admin'

def is_user():
    return current_user and current_user['role'] == 'user'

# Flask routes
@app.route('/')
def index():
    global time_on, time_off
    return render_template('login.html', time_on=time_on, time_off=time_off)

@app.route('/set_times', methods=['GET', 'POST'])
def set_times():
    global time_on, time_off
    if is_authenticated():
        if is_admin():
            try:
                if request.method == 'POST':
                    time_on = request.form['time_on']
                    time_off = request.form['time_off']
                    last_set_times['time_on'] = time_on
                    last_set_times['time_off'] = time_off
                    save_last_set_times()
                    flash('Times updated successfully', 'success')

                    # Add the following line to display an alert
                    return render_template('set.html', time_on=time_on, time_off=time_off, alert_message="Time set successfully!")
                return render_template('set.html', time_on=time_on, time_off=time_off)
            except Exception as e:
                print(f"Error in set_times route: {e}")
                print(format_exc())
                flash('An error occurred while updating times', 'error')
                return render_template('set.html', time_on=time_on, time_off=time_off)
        else:
            return redirect(url_for('show_times'))
    else:
        return redirect(url_for('login'))

# ... (remaining code)

@app.route('/get_light_state')
def get_light_state():
    if is_authenticated():
        light_state = GPIO.input(LIGHT_PIN)
        return jsonify({'light_state': light_state})
    else:
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    global current_user
    login_message = ""

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users and users[username]['password'] == password:
            current_user = users[username]

            if is_admin():
                return redirect(url_for('set_times'))
            else:
                return redirect(url_for('show_times'))

        login_message = "Incorrect username or password. Please try again."

    if is_authenticated():
        if is_admin():
            return redirect(url_for('set_times'))
        else:
            return redirect(url_for('show_times'))

    return render_template('login.html', login_message=login_message)

@app.route('/show_times')
def show_times():
    if is_authenticated():
        return render_template('show_times.html', time_on=time_on, time_off=time_off)
    else:
        return redirect(url_for('login'))

# Main function
def check_time():
    global time_on, time_off
    while True:
        try:
            with open('last_set_times.json', 'r') as file:
                last_set_times = json.load(file)
                time_on = last_set_times['time_on']
                time_off = last_set_times['time_off']
        except (FileNotFoundError, json.JSONDecodeError):
            last_set_times = {'time_on': None, 'time_off': None}

        current_time = datetime.now().strftime("%H:%M")

        if time_on and time_off and time_on is not None and time_off is not None:
            time_on_dt = datetime.strptime(time_on, "%H:%M")
            time_off_dt = datetime.strptime(time_off, "%H:%M")
            buffer_time = timedelta(seconds=BUFFER_TIME)

            current_time_dt = datetime.strptime(current_time, "%H:%M")

            if time_on_dt - buffer_time <= current_time_dt <= time_off_dt + buffer_time:
                turn_on_light()
            else:
                turn_off_light()

        # Check the time every minute
        time.sleep(60)

# Application setup and run
if __name__ == "__main__":
    setup()
    try:
        import threading
        t = threading.Thread(target=check_time)
        t.start()
        app.run(host='0.0.0.0', port=5001)
    except KeyboardInterrupt:
        GPIO.cleanup()
