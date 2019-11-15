#!/usr/bin/env python

import logging
import os
import subprocess
import time
from datetime import datetime

from flask import (Flask, abort, redirect, render_template, request,
                   send_from_directory, url_for)
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)

cv_last_build = None
last_login = 0
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


@app.route('/timetable')
def calendar():
    return render_template('timetable.html')


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.route('/login', methods=['GET', 'POST'])
def login():
    global last_login
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'GET':
        return render_template('login.html')
    elif request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        app.logger.info('login user: {}, pass: {}'.format(username, password))
        time.sleep(0.5)
        if username == MASTER_USERNAME and password == MASTER_PASSWORD and time.time() - last_login > 5:
            last_login = time.time()
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


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/robots.txt')
def robots():
    return send_from_directory('static', 'robots.txt')


def guess_file_icon(filename):
    if filename.endswith('/'):
        return 'folder'
    if filename.endswith('.mp4'):
        return 'movie'
    if filename == '../':
        return 'folder_open'
    return 'note'


def construct_fs_entry(entry, path, timestamp=None):
    if timestamp is not None:
        utc = datetime.utcfromtimestamp(timestamp)
        raw_datetime = utc.strftime('%Y-%m-%dT%H:%M:%S')
        formatted = utc.strftime('%Y-%m-%d %I:%M %p')
    else:
        formatted = raw_datetime = ''
    return (entry, path, formatted, raw_datetime)


def get_file_from(directory, login=False):
    endpoint = directory

    def func(name):
        full_name = os.path.realpath(
            os.path.join(os.getcwd(), directory, name))
        full_dirname = os.path.abspath(directory)

        # path occurs outside of this served directory
        if os.path.commonprefix((full_dirname, full_name)) != full_dirname:
            abort(404)

        if not os.path.exists(full_name):
            abort(404)

        # if it's a file, just send it
        if os.path.isfile(full_name):
            app.logger.info('sending {}'.format(name))
            return send_from_directory(directory, name)

        # otherwise send the directory representation
        entries = []
        for entry in os.listdir(os.path.join(os.getcwd(), full_name)):
            path = os.path.join(name, entry)
            abspath = os.path.join(os.getcwd(), directory, path)
            if os.path.isdir(abspath):
                entry += '/'
            mtime = os.path.getmtime(abspath)
            entries.append((entry, path, mtime))
        entries.sort(key=lambda x: x[0])
        entries = [construct_fs_entry(*entry) for entry in entries]
        if full_dirname != full_name:
            back_entry = construct_fs_entry('../', os.path.join('name', '..'))
            entries.insert(0, back_entry)
        return render_template('folder.html', title=directory,
                               endpoint=endpoint, entries=entries,
                               guesser=guess_file_icon)

    if login:
        func = login_required(func)
    app.add_url_rule('/{}/<path:name>'.format(directory), endpoint, func)
    app.add_url_rule('/{}/'.format(directory), endpoint,
                     func, provide_automatic_options=None, defaults={'name': ''})


get_file_from('private_static', login=True)
get_file_from('anime')
get_file_from('music')

if __name__ == '__main__':
    app.debug = True
    app.run()
else:
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers

    app.logger.setLevel(gunicorn_logger.level)
