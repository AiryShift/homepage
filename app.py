import os
import time

from flask import Flask, redirect, render_template, send_from_directory, url_for

cv_last_build = None
BUILD_INTERVAL = 60 * 60
app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/cv')
def cv():
    if cv_last_build is None or time.time() - cv_last_build > BUILD_INTERVAL:
        app.logger.info('Building cv')
        original_wd = os.getcwd()
        try:
            os.chdir(os.path.join(os.getcwd(), 'cv'))
            os.system('git pull')
            os.system('pdflatex cv.tex')
            os.system('mv cv.pdf ../static/')
        finally:
            os.chdir(original_wd)
    return redirect(url_for('static', filename='cv.pdf'))


if __name__ == '__main__':
    app.run()
