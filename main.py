from flask import Flask, render_template, request, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
from sqlalchemy import Index
import csv
from io import StringIO
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("SQLALCHEMY_DATABASE_URI")
db = SQLAlchemy(app)


class User(db.Model):
    # user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    email = db.Column(db.String(120), primary_key=True, nullable=False)
    phone = db.Column(db.String(10), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)

    __table_args__ = (Index('ix_user_email', 'email'),)

class Expense(db.Model):
    user_email = db.Column(db.String(120), db.ForeignKey(User.email))
    expense_id = db.Column(db.Integer, primary_key=True)
    expense_name = db.Column(db.String(120), nullable=False)
    total_spent = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default = datetime.now)

    # adding index to the user email column as it'll used frequently and this will make queries faster
    __table_args__ = (Index('ix_expense_user_email', 'user_email'),)

class Participants(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_email = db.Column(db.String(120), db.ForeignKey(User.email))
    expense_id = db.Column(db.Integer, db.ForeignKey(Expense.expense_id))
    participant_name = db.Column(db.String(120), nullable=False)
    share = db.Column(db.Float, nullable=False)
    share_type = db.Column(db.String(120), nullable=False)  # i want this to be an enum

    __table_args__ = (Index('ix_participants_user_email', 'user_email'),)

@app.route('/')
def index():
    return "<h1>Hello Convin! This is the assignment task for backend developer intern done by Adithya Pillai</h1>"


@app.route('/register',methods=['POST'])
def register():
    auth = request.form
    email = auth.get('email')
    name =  auth.get('name')
    phone = auth.get('phone')
    password = auth.get('password')
    user = User.query.filter_by(email=email).first()
    if user:
        return jsonify({"message":"account already exists!!"}), 400
    else:
        new_user = User(name=name, email=email, phone=phone, password=password)
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"message":"new user created successfully!"}), 201


@app.route("/expense",methods=['POST'])
def setExpense():
    auth = request.form
    email = auth.get('email')
    expense_name = auth.get('expense_name')
    totalspent = float(auth.get('total'))
    share_type = auth.get('share_type')
    participants_str = auth.get('participants')
    participants = [participant.strip() for participant in participants_str.split(',') if participant.strip()]

    if not all([email, expense_name, totalspent, share_type, participants_str]):
        return jsonify({"message":"Missing required fields"}), 400
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"message":"account doesn't exists!!"}), 400
    # Create and add the new expense
    new_expense = Expense(user_email=email, expense_name=expense_name, total_spent=totalspent)
    db.session.add(new_expense)
    db.session.flush()  # This will assign the expense_id without committing

    # Get the new expense_id
    new_expense_id = new_expense.expense_id
    
    if share_type == "EQUAL":
        share = totalspent / len(participants)
        # Add participants
        for participant in participants:
            new_participant = Participants(
                user_email=email,
                expense_id=new_expense_id,
                participant_name=participant,
                share=share,
                share_type='EQUAL'
            )
            db.session.add(new_participant)
    elif share_type == "EXACT":
        indiv_share_str = auth.get("exact_share")
        individual_shares = [float(share.strip()) for share in indiv_share_str.split(',') if share.strip()]
        if len(individual_shares) != len(participants):
                return jsonify({"message":"Number of shares doesn't match number of participants"}), 400
        for i in range(len(participants)):
            new_participant = Participants(
                user_email=email,
                expense_id=new_expense_id,
                participant_name=participants[i],
                share=individual_shares[i],
                share_type='EXACT'
            )
            db.session.add(new_participant)
    elif share_type == "PERCENT":
        indiv_share_percent_str = auth.get("percent_share")
        individual_shares_percent = [float(share.strip()) for share in indiv_share_percent_str.split(',') if share.strip()]
        if len(individual_shares_percent) != len(participants):
                return jsonify({"message":"Number of percentages doesn't match number of participants"}), 400
        elif sum(individual_shares_percent) != 100:
            return jsonify({"message":"Number of percentages don't add up to 100"}), 400
        
        for i in range(len(participants)):
            new_participant = Participants(
                user_email=email,
                expense_id=new_expense_id,
                participant_name=participants[i],
                share=totalspent*(individual_shares_percent[i]*0.01),
                share_type='PERCENT'
            )
            db.session.add(new_participant)
    else:
        return jsonify({
            "message": "Share type is not valid!"
        }), 400

    # Commit all changes
    db.session.commit()

    return jsonify({
        "message": "Expense created successfully",
        "expense_id": new_expense_id,
        "share_type": share_type
    }), 201


@app.route("/retrieval/individual/<string:participant_name>",methods=['POST'])
def retrieve_individual(participant_name):
    auth = request.form
    email = auth.get('email')
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"message":"account doesn't exists!!"}), 400
    individual_expenses =  db.session.query(func.sum(Participants.share))\
        .filter(Participants.user_email == email)\
        .filter(Participants.participant_name == participant_name)
        
    # print(individual_expenses)
    if individual_expenses:
        return jsonify({"message": "successfully got the cumulative sum of a particular participant!",
                        "participant": participant_name,
                        "total sum": individual_expenses.scalar()}), 200 # scalar gives a single value, cause individual_expenses is a result set
    else:
        return jsonify({"message":"No such user found from your profile!"}), 400


@app.route("/retrieval/overall",methods=['POST'])
def retrieve_overall():
    auth = request.form
    email = auth.get('email')
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"message":"account doesn't exists!!"}), 400
    expenses =  db.session.query(func.sum(Expense.total_spent))\
        .filter(Expense.user_email == email)\
        .scalar()
    if expenses:
        return jsonify({"message":"successfully got the total spent from this account",
                        "email":email,
                        "expenses":expenses}), 200



@app.route("/balance_sheet", methods=['GET'])
def generate_balance_sheet():
    auth = request.form
    email = auth.get('email')
    if not email:
        return jsonify({"error": "Email is required"}), 400
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"message":"account doesn't exists!!"}), 400
    # Fetch all expenses for this user
    expenses = Expense.query.filter_by(user_email=email).all()
    if not expenses:
        return jsonify({"message":"Your account doesn't have any expenses!"}), 400
    
    # Create a StringIO object to write our CSV to
    si = StringIO()
    cw = csv.writer(si)

    # Write the header
    cw.writerow(['expense name', 'date', 'total spent', 'participant names', 'participant shares', 'share type'])

    # Write the data
    for expense in expenses:
        participants = Participants.query.filter_by(expense_id=expense.expense_id).all()
        
        # Write the first participant row with expense details
        first_participant = participants[0]
        cw.writerow([
            expense.expense_name,
            expense.date.strftime('%Y-%m-%d %H:%M:%S'),
            expense.total_spent,
            first_participant.participant_name,
            first_participant.share,
            first_participant.share_type
        ])
        
        # Write the remaining participants
        for participant in participants[1:]:
            cw.writerow([
                '',  # Empty expense name
                '',  # Empty date
                '',  # Empty total spent
                participant.participant_name,
                participant.share,
                ''
            ])
        
        # Add an empty row between expenses for readability
        cw.writerow([])

    # Create the response
    response = make_response(si.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=balance_sheet.csv'
    response.headers['Content-type'] = 'text/csv'

    return response


with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
 