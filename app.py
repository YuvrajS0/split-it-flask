from flask import Flask, redirect, url_for, session, render_template, request, flash
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, joinedload
from models import Base, Receipt, Item, Person
import os

# Load environment variables
load_dotenv()

app = Flask(__name__)

USER = os.getenv("user")
PASSWORD = os.getenv("password")
HOST = os.getenv("host")
PORT = os.getenv("port")
DBNAME = os.getenv("dbname")
DATABASE_URL = f"postgresql+psycopg2://{USER}:{PASSWORD}@{HOST}:{PORT}/{DBNAME}?sslmode=require"
engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

app.secret_key = os.getenv('SECRET_KEY', 'your_secret_key')
app.config['SESSION_TYPE'] = 'redis'
app.config['GITHUB_CLIENT_ID'] = os.getenv('GITHUB_CLIENT_ID')
app.config['GITHUB_CLIENT_SECRET'] = os.getenv('GITHUB_CLIENT_SECRET')

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
    return render_template('home.html', user=session['user'])

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

    db_session = Session()
    receipts = db_session.query(Receipt)\
        .options(joinedload(Receipt.items).joinedload(Item.people),
                 joinedload(Receipt.people))\
        .all()

    detailed_receipts = []

    for receipt in receipts:
        receipt_items = receipt.items
        receipt_people = receipt.people
        total_price = sum(item.price for item in receipt_items)
        person_breakdown = {}

        for person in receipt_people:
            subtotal = 0
            item_shares = []
            for item in receipt_items:
                if person in item.people and item.people:
                    share = item.price / len(item.people)
                    subtotal += share
                    item_shares.append({'name': item.name, 'share': round(share, 2)})

            tax_tip_share = (subtotal / total_price) * receipt.tax_tip if total_price else 0
            person_breakdown[person.name] = {
                'subtotal': round(subtotal, 2),
                'tax_tip_share': round(tax_tip_share, 2),
                'total': round(subtotal + tax_tip_share, 2),
                'item_shares': item_shares
            }

        detailed_receipts.append({
            'receipt': receipt,
            'person_breakdown': person_breakdown
        })

    return render_template('profile.html', detailed_receipts=detailed_receipts)

@app.route('/logout')
def logout():
    session.clear()
    session.modified = True
    return redirect(url_for('login'))

@app.route('/breakdown', methods=['POST'])
def breakdown():
    receipt_name = request.form['receipt_name']
    tax_tip = float(request.form['tax_tip'])
    people = [name for name in request.form.getlist('person_names[]') if name.strip()]
    item_names = request.form.getlist('item_names[]')
    item_prices = request.form.getlist('item_prices[]')
    assignments = request.form.getlist('assignments[]')

    items = []
    for i in range(len(item_names)):
        if not item_names[i].strip():
            continue
        assignment = assignments[i].strip()
        items.append({
            'name': item_names[i],
            'price': float(item_prices[i]),
            'assignment': assignment
        })

    person_totals = {name: 0.0 for name in people}
    for item in items:
        if item['assignment'] == 'all':
            share = item['price'] / len(people)
            for name in people:
                person_totals[name] += share
        else:
            try:
                indices = list(map(int, item['assignment'].split(',')))
                assigned = [people[i] for i in indices if 0 <= i < len(people)]
                if assigned:
                    share = item['price'] / len(assigned)
                    for name in assigned:
                        person_totals[name] += share
            except:
                continue

    total = sum(item['price'] for item in items)
    for name in people:
        person_totals[name] += (person_totals[name] / total) * tax_tip

    return render_template('breakdown.html', receipt_name=receipt_name, tax_tip=tax_tip,
                           people=people, items=items, breakdown=person_totals)



@app.route('/save_receipt', methods=['POST'])
def save_receipt():
    session_db = Session()
    receipt_name = request.form['receipt_name']
    tax_tip = float(request.form['tax_tip'])
    receipt = Receipt(name=receipt_name, tax_tip=tax_tip)
    session_db.add(receipt)

    people_names = request.form.getlist('person_names[]')
    item_names = request.form.getlist('item_names[]')
    item_prices = request.form.getlist('item_prices[]')
    assignments = request.form.getlist('assignments[]')

    people = [Person(name=name, receipt=receipt) for name in people_names if name.strip()]
    for p in people:
        session_db.add(p)

    for i in range(len(item_names)):
        if not item_names[i].strip():
            continue
        item = Item(name=item_names[i], price=float(item_prices[i]), receipt=receipt)
        indices_raw = assignments[i].strip()
        if indices_raw == 'all':
            for person in people:
                item.people.append(person)
        elif indices_raw:
            try:
                indices = list(map(int, indices_raw.split(',')))
                for idx in indices:
                    if 0 <= idx < len(people):
                        item.people.append(people[idx])
            except ValueError:
                pass
        session_db.add(item)

    session_db.commit()
    return redirect(url_for('profile'))

from flask import flash

@app.route('/delete_receipt/<int:receipt_id>', methods=['POST'])
def delete_receipt(receipt_id):
    if 'user' not in session:
        return redirect(url_for('login'))

    db_session = Session()
    receipt = db_session.query(Receipt).filter_by(id=receipt_id).first()

    if not receipt:
        flash('Receipt not found.', 'danger')
        return redirect(url_for('profile'))

    # Delete related items if needed, or configure cascade in models
    db_session.delete(receipt)
    db_session.commit()
    flash('Receipt deleted successfully.', 'success')

    return redirect(url_for('profile'))

if __name__ == '__main__':
    app.run()
