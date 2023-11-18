import RPi.GPIO as GPIO
import time
from datetime import datetime, timedelta
from flask import Flask, flash, request, render_template, jsonify, redirect, url_for

import json
import secrets
import os

app = Flask(__name__)
secret_key = secrets.token_hex(16)

# Set it as the Flask app's secret key
app.secret_key = secret_key

GPIO.setmode(GPIO.BCM)

# Define GPIO pins for relay control
relay_pins = [2, 3, 4, 18]

for pin in relay_pins:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

# Configuration
LIGHT_PIN = 17  # Change this to the GPIO pin connected to the relay module

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
    'light': {
        'username': 'light',
        'role': 'light',
        'password': 'light',
    }
}


@app.route('/admin')
def admin():
    if is_admin():
        return render_template('set.html')
    else:
        return redirect(url_for('login'))

# Route for the user page
@app.route('/user')
def user():
    if is_user():
        return render_template('show_times.html')
    else:
        return redirect(url_for('login'))

@app.route('/light')
def light():
    if is_light():
        return render_template('4channel.html')
    else:
        return redirect(url_for('login'))



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

@app.route('/')
def index():
    global time_on, time_off  # Use the global keyword to access and modify global variables
    return render_template('login.html', time_on=time_on, time_off=time_off)


@app.route('/set_times', methods=['GET', 'POST'])
def set_times():
    global time_on, time_off  # Use the global keyword to access and modify global variables
    if is_authenticated():
        if is_admin():
            if request.method == 'POST':
                time_on = request.form['time_on']
                time_off = request.form['time_off']
                last_set_times['time_on'] = time_on
                last_set_times['time_off'] = time_off
                save_last_set_times()
                flash('Times updated successfully', 'success')  # Add a success message
            return render_template('set.html', time_on=time_on, time_off=time_off)
        else:
            return redirect(url_for('show_times'))
    else:
        return redirect(url_for('login'))


@app.route('/get_light_state')
def get_light_state():
    if is_authenticated():
        light_state = GPIO.input(LIGHT_PIN)
        return jsonify({'light_state': light_state})
    else:
        return redirect(url_for('login'))

@app.route('/control_relay', methods=['POST'])
def control_relay():
    if is_light():
        relay_num = int(request.form['relay_num'])
        relay_state = request.form['relay_state']

        if 1 <= relay_num <= 4 and relay_state in ['on', 'off']:
            pin = relay_pins[relay_num - 1]
            if relay_state == 'on':
                GPIO.output(pin, GPIO.HIGH)
            else:
                GPIO.output(pin, GPIO.LOW)
            return jsonify({'success': True, 'message': f'Relay {relay_num} turned {relay_state}'})
        else:
            return jsonify({'success': False, 'message': 'Invalid relay number or state'})
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
                return redirect(url_for('set_times'))  # Redirect the admin user to the set_times page
            elif is_user():
                return redirect(url_for('show_times'))
            else:
                return redirect(url_for('light'))

        login_message = "Incorrect username or password. Please try again."

    return render_template('login.html', login_message=login_message)


@app.route('/show_times')
def show_times():
    if is_authenticated():
        return render_template('show_times.html', time_on=time_on, time_off=time_off)  # Pass time_on and time_off to the template
    else:
        return redirect(url_for('login'))

def is_authenticated():
    return current_user is not None

def is_admin():
    return current_user and current_user['role'] == 'admin'

def is_user():
    return current_user and current_user['role'] == 'user'

def is_light():
    return current_user and current_user['role'] == 'light'

def check_time():
    while True:
        current_time = datetime.now().strftime("%H:%M")

        if time_on and time_off:
            time_on_dt = datetime.strptime(time_on, "%H:%M")
            time_off_dt = datetime.strptime(time_off, "%H:%M")
            buffer_time = timedelta(seconds=BUFFER_TIME)

            if time_on_dt - buffer_time <= datetime.strptime(current_time, "%H:%M") <= time_on_dt + buffer_time:
                turn_on_light()
            elif time_off_dt - buffer_time <= datetime.strptime(current_time, "%H:%M") <= time_off_dt + buffer_time:
                turn_off_light()
        time.sleep(60)  # Check the time every minute


if __name__ == "__main__":
    setup()
    try:
        import threading
        t = threading.Thread(target=check_time)
        t.start()
        app.run(host='0.0.0.0', port=5001)
    except KeyboardInterrupt:
        GPIO.cleanup()