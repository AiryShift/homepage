#!/usr/bin/env python

import os
import subprocess
import time

from flask import (Flask, abort, redirect, render_template, request,
                   send_from_directory, url_for)
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)

cv_last_build = None
BUILD_INTERVAL = 60 * 60
MASTER_USERNAME = os.environ.get('MASTER_USERNAME', default='admin')
MASTER_PASSWORD = os.environ.get('MASTER_PASSWORD', default='admin')
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', default=os.urandom(16))

login_manager = LoginManager()
login_manager.init_app(app)


class User(UserMixin):
    def get_id(self):
        return '0'


MASTER_USER = User()


@login_manager.user_loader
def load_user(user_id):
    return MASTER_USER


@app.route('/')
def index():
    return render_template('index.html')


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'GET':
        return render_template('login.html')
    elif request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        app.logger.info('login user: {}, pass: {}'.format(username, password))
        time.sleep(0.5)
        if username == MASTER_USERNAME and password == MASTER_PASSWORD:
            login_user(MASTER_USER, remember=True)
            next_url = request.args.get('next')
            return redirect(next_url or url_for('index'))
        return render_template('login.html', failed_login=True)
    abort(404)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@login_manager.unauthorized_handler
def unauthorized():
    abort(404)


def build_cv():
    global cv_last_build
    app.logger.info('Building cv')
    original_wd = os.getcwd()
    try:
        os.chdir(os.path.join(os.getcwd(), 'cv'))
        subprocess.run('git pull && pdflatex cv.tex', shell=True)
        subprocess.run('mv cv.pdf ../static/', shell=True)
    except OSError:
        subprocess.run('touch ../static/cv.pdf')
    else:
        cv_last_build = time.time()
    finally:
        os.chdir(original_wd)


@app.route('/cv')
def cv():
    if cv_last_build is None or time.time() - cv_last_build > BUILD_INTERVAL:
        build_cv()
    return redirect(url_for('static', filename='cv.pdf'))


@app.route('/rebuild_cv')
def rebuild_cv():
    build_cv()
    return redirect(url_for('cv'))


@app.route('/private_static')
@login_required
def private_static():
    static_dir = os.path.join(os.getcwd(), 'private_static')
    fs = []
    for root, _, filenames in os.walk(static_dir):
        for filename in filenames:
            real_path = os.path.join(root, filename)
            stripped = os.path.relpath(real_path, start=static_dir)
            fs.append(stripped)
    return render_template('private_static.html', fs=fs)


def get_file_from(path, login=False):
    def func(name):
        return send_from_directory(path, name)
    if login:
        func = login_required(func)
    rule = '/{}/<path:name>'.format(path)
    endpoint = 'get_file_from_{}'.format(path)
    app.add_url_rule(rule, endpoint, func)

get_file_from('private_static', login=True)
get_file_from('anime')

if __name__ == '__main__':
    app.debug = True
    app.run()
