from flask import Flask, redirect, url_for, session, render_template
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
import os
from flask_session import Session

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure app settings
app.secret_key = os.getenv('SECRET_KEY', 'your_secret_key')
app.config['SESSION_TYPE'] = 'redis'
app.config['GITHUB_CLIENT_ID'] = os.getenv('GITHUB_CLIENT_ID', 'your_github_client_id')
app.config['GITHUB_CLIENT_SECRET'] = os.getenv('GITHUB_CLIENT_SECRET', 'your_github_client_secret')

# Initialize Flask-Session after configuration
Session(app)

oauth = OAuth(app)

github = oauth.register(
    name='github',
    client_id=app.config['GITHUB_CLIENT_ID'],
    client_secret=app.config['GITHUB_CLIENT_SECRET'],
    access_token_url='https://github.com/login/oauth/access_token',
    authorize_url='https://github.com/login/oauth/authorize',
    api_base_url='https://api.github.com/',
    client_kwargs={'scope': 'user:email'},
)

@app.route('/')
def home():
    if 'user' not in session:
        return redirect(url_for('login'))
    user_info = session['user']
    return render_template('home.html', user=user_info)

@app.route('/login')
def login():
    return github.authorize_redirect(url_for('authorize', _external=True))

@app.route('/authorize')
def authorize():
    token = github.authorize_access_token()
    user_info = github.get('user').json()
    session['user'] = user_info
    return redirect(url_for('home'))

@app.route('/profile')
def profile():
    if 'user' not in session:
        return redirect(url_for('login'))
    user_info = session['user']
    return render_template('profile.html', user=user_info)

@app.route('/logout')
def logout():
    session.clear()
    session.modified = True 
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)