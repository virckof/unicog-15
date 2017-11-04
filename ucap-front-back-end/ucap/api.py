#!/home/ubuntu/ucap/ucap_venv/bin/python
from ucap import app
from flask import jsonify, abort, make_response, request, g, Response
from werkzeug.security import generate_password_hash, check_password_hash
import random
import string
import json
import os, os.path
import hashlib
from functools import wraps
import base64
import time
import datetime
import DBManager

MAX_TEXT_FIELD_LEN = 32
MAX_TEXTAREA_LEN = 10000
MAX_EMAIL_LEN = 255
MIN_PASSWORD_LEN = 6


#---------
# Wrapper
#---------

def is_logged_in(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'sessionID' in request.cookies and DBManager.check_session(request.cookies['sessionID']) == 1:
            return func(*args, **kwargs)
        else:
            abort(401)
    return wrapper


#------------
# API Proper
#------------

#----------
## Sessions
#----------

@app.route('/api/login', methods=['POST'])
def login():

    # Can't be triggered by normal app use
    if not all(param in request.json for param in ('username', 'password')):
        return jsonify({'errors': {'missing_fields': 'Please supply all required fields'}}), 400

    username = request.json['username']
    password = request.json['password']

    errors = {}
    session_id_str = ""
    password_hash = DBManager.get_tester_password_hash(username)
    is_active = DBManager.is_tester_active(username)
    if password_hash and check_password_hash(password_hash, password) and is_active:
        session_id = generate_session_id()
        insert_id = DBManager.create_session(session_id.hexdigest(), username)
        # insert_id should never be None; this can only happen if the
        # tester is deleted after the first DBManager function call but before
        # the second
        if insert_id != None: 
            session_id_str = session_id.hexdigest()
        else:
            errors['username_or_password'] = 'Invalid username or password'
    else:
        errors['username_or_password'] = 'Invalid username or password'

    if bool(errors) == True:
        response = jsonify({'errors': errors})
        status_code = 401
    else:
        response = jsonify({})
        response.set_cookie('sessionID', session_id_str)
        status_code = 200
    return response, status_code


@app.route('/api/logout', methods=['POST'])
def logout():
    session_id = request.cookies['sessionID']
    DBManager.delete_session(session_id)
    return jsonify({}), 200
 

@app.route('/api/check_session', methods=['POST'])
def check_session():
    if 'sessionID' in request.cookies and DBManager.check_session(request.cookies['sessionID']) == 1:
        return jsonify({'is_logged_in': True}), 200
    else:
        return jsonify({'is_logged_in': False}), 200


#-------
## Tests
#-------

@app.route('/api/create_completed_test', methods=['POST'])
@is_logged_in
def create_test():

    # Can't be triggered by normal app use
    if not all(param in request.json for param in ('app', 'patient_id', 'test_date')):
        return jsonify({'errors': {'missing_fields': 'Please supply all required fields'}}), 400

    test = {
        'app': request.json['app'],
        'patient_id': int(request.json['patient_id']),
        'tester_id': DBManager.get_logged_in_tester_id(request.cookies['sessionID']),
        'test_date': request.json['test_date']
        }

    if test['patient_id'] == 0:
        test['patient_id'] = DBManager.create_patient({ 'patient_type': 'anonymous',
                                                        'visible_patient_id': datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S'),
                                                        'group': '',
                                                        'name': '',
                                                        'dob': '',
                                                        'notes': '',
                                                        'gender': '',
                                                        'password_hash': '' })

    test['details'] = {}
    for key, value in request.json.iteritems():
        if key not in test:
            test['details'][key] = value

    try:
        globals()[test['app']+'_post_process'](test)
    except KeyError, NameError:
        # Post-processing functions aren't defined for all the games 
        pass

    insert_id = DBManager.create_test(test)

    return_array = {'test_id': insert_id}
    if int(request.json['patient_id']) == 0:
        return_array['patient_id'] = test['patient_id']

    return jsonify(return_array), 201


@app.route('/api/get_tests', methods=['GET'])
@is_logged_in
def get_tests():

    # Can't be triggered by normal app use
    if not all(param in request.args for param in ('app_code', )):
        return jsonify({'errors': {'missing_fields': 'Please supply all required fields'}}), 400

    app_code = request.args.get('app_code')
    query = request.args.get('query') if 'query' in request.args else None

    tests = DBManager.get_tests(app_code=app_code, query=query)

    for test in tests:
        test['visible_patient_id'] = DBManager.get_visible_patient_id(test['patient_id'])
        tester = DBManager.get_tester(test['tester_id'])
        test['tester_username'] = tester['username']
        test['tester_first_name'] = tester['first_name']
        test['tester_last_name'] = tester['last_name']

    return jsonify({"Tests": tests})


#----------
## Patients
#----------

@app.route('/api/create_patient', methods=['POST'])
@is_logged_in
def create_patient():

    # Can't be triggered by normal app use
    if not all(param in request.json for param in ('visible_patient_id', )):
        return jsonify({'errors': {'missing_fields': 'Please supply all required fields'}}), 400

    if 'group' not in request.json:
        request.json['group'] = ''
    if 'name' not in request.json:
        request.json['name'] = ''
    if 'dob' not in request.json:
        request.json['dob'] = ''
    if 'notes' not in request.json:
        request.json['notes'] = ''
    if 'gender' not in request.json:
        request.json['gender'] = ''

    errors = {}

    # Presence and length validation
    if len(request.json['visible_patient_id']) == 0:
        errors['visible_patient_id'] = 'ID can\'t be empty'
    elif len(request.json['visible_patient_id']) > MAX_TEXT_FIELD_LEN:
        errors['visible_patient_id'] = 'ID can\'t be longer than '+str(MAX_TEXT_FIELD_LEN)+' characters'
    if 'patient_type' not in request.json:
        errors['patient_type'] = 'Patient type can\'t be empty'
    if len(request.json['group']) > MAX_TEXT_FIELD_LEN:
        errors['group'] = 'Group can\'t be longer than '+str(MAX_TEXT_FIELD_LEN)+' characters'
    if len(request.json['name']) > MAX_TEXT_FIELD_LEN:
        errors['name'] = 'Name can\'t be longer than '+str(MAX_TEXT_FIELD_LEN)+' characters'
    if len(request.json['notes']) > MAX_TEXTAREA_LEN:
        errors['notes'] = 'Notes can\'t be longer than '+str(MAX_TEXTAREA_LEN)+' characters'

    # Uniqueness validation
    if 'visible_patient_id' not in errors and DBManager.is_visible_patient_id_unique(request.json['visible_patient_id']) == False:
        errors['visible_patient_id'] = 'ID already exists'

    # Integrity validation
    if 'patient_type' not in errors and 'patient_type' in request.json and request.json['patient_type'] not in ('blind', 'non-blind'):
        errors['patient_type'] = 'Invalid patient type'
    if 'gender' not in errors and request.json['gender'] != 'female' and request.json['gender'] != 'male' and request.json['gender'] != '':
        errors['gender'] = 'Invalid gender'
    if 'dob' not in errors and not is_valid_dob(request.json['dob']) and request.json['dob'] != '':
        errors['dob'] = 'Invalid DOB'


    if bool(errors) == False:

        patient_password = random_word(8)

        patient = {
            'patient_type': request.json['patient_type'],
            'visible_patient_id': request.json['visible_patient_id'],
            'group': request.json['group'],
            'name': request.json['name'],
            'gender': request.json['gender'],
            'dob': request.json['dob'],
            'notes': request.json['notes'],
            'password_hash': generate_password_hash(patient_password)
            }

        insert_id = DBManager.create_patient(patient)
        tester_id = DBManager.get_logged_in_tester_id(request.cookies['sessionID'])
        DBManager.unlock_patient(tester_id, insert_id)

        return_info = {
            'id': insert_id,
            }
        if patient['patient_type'] == 'non-blind':
            return_info['password'] = patient_password
        return jsonify(return_info), 201

    else:
        return jsonify({'errors': errors}), 400


@app.route('/api/get_patient', methods=['GET'])
@is_logged_in
def get_patient():

    # Can't be triggered by normal app use
    if not all(param in request.args for param in ('patient_id', )):
        return jsonify({'errors': {'missing_fields': 'Please supply all required fields'}}), 400

    patient_id = int(request.args.get('patient_id'))
    tester_id = DBManager.get_logged_in_tester_id(request.cookies['sessionID'])

    patient = DBManager.get_patient(patient_id, tester_id)
    if patient == None:
        abort(404)

    return jsonify({'Patient': patient})


@app.route('/api/get_patients', methods=['GET'])
@is_logged_in
def get_patients():

    # Can't be triggered by normal app use
    if not all(param in request.args for param in ('test_selection', )):
        return jsonify({'errors': {'missing_fields': 'Please supply all required fields'}}), 400

    tester_id = DBManager.get_logged_in_tester_id(request.cookies['sessionID'])
    # tester_id should never be None; this can only happen if the
    # tester is deleted after the first DBManager function call
    # (i.e. in is_logged_in) but before the second
    if tester_id == None:
        tester_id = -1

    patient_type = request.args.get('patient_type') if 'patient_type' in request.args else None
    test_selection = int(request.args.get('test_selection')) == 1

    patients = DBManager.get_patients(tester_id, patient_type=patient_type, test_selection=test_selection)

    return jsonify({"Patients": patients})


@app.route('/api/get_visible_patient_ids', methods=['GET'])
@is_logged_in
def get_visible_patient_ids():
    return jsonify({"visible_patient_ids": DBManager.get_visible_patient_ids()})


@app.route('/api/unlock_patient', methods=['POST'])
@is_logged_in
def unlock_patient():

    # Can't be triggered by normal app use
    if not all(param in request.json for param in ('patient_id', 'password')):
        return jsonify({'errors': {'missing_fields': 'Please supply all required fields'}}), 400

    patient_id = int(request.json['patient_id'])
    password = request.json['password']

    password_hash = DBManager.get_patient_password_hash(patient_id)
    is_blind = DBManager.is_patient_blind(patient_id)

    if password_hash and check_password_hash(password_hash, password) and not is_blind:
        tester_id = DBManager.get_logged_in_tester_id(request.cookies['sessionID'])
        DBManager.unlock_patient(tester_id, patient_id)
        response = jsonify({'unlock_successful': True})
    else:
        response = jsonify({'unlock_successful': False})

    return response, 201


@app.route('/api/search_patients', methods=['GET'])
@is_logged_in
def search_patients():

    # Can't be triggered by normal app use
    if not all(param in request.args for param in ('query', )):
        return jsonify({'errors': {'missing_fields': 'Please supply all required fields'}}), 400

    tester_id = DBManager.get_logged_in_tester_id(request.cookies['sessionID'])
    # tester_id should never be None; this can only happen if the
    # tester is deleted after the first DBManager function call
    # (i.e. in is_logged_in) but before the second
    if tester_id == None:
        tester_id = -1

    query = request.args.get('query')

    patients = DBManager.search_patients(tester_id, query, False)

    return jsonify({"Patients": patients})


#---------
## Testers
#---------

@app.route('/api/create_tester', methods=['POST'])
def create_tester():

    # Can't be triggered by normal app use
    if not all(param in request.json for param in ('email', 'organization', 'username', 'first_name', 'last_name', 'password', 'password_again')):
        return jsonify({'errors': {'missing_fields': 'Please supply all required fields'}}), 400

    email = request.json['email']
    organization = request.json['organization']
    username = request.json['username'].lower()
    first_name = request.json['first_name']
    last_name = request.json['last_name']
    password = request.json['password']
    password_again = request.json['password_again']

    send_email=False

    errors = {}
    insert_id = -1

    # Presence and length validation
    if len(email) == 0:
        errors['email'] = 'Email can\'t be empty'
    elif len(email) > MAX_EMAIL_LEN:
        errors['email'] = 'Email can\'t be longer than '+str(MAX_EMAIL_LEN)+' characters'
    if len(organization) == 0:
        errors['organization'] = 'Organization can\'t be empty'
    elif len(organization) > MAX_TEXT_FIELD_LEN:
        errors['organization'] = 'Organization can\'t be longer than '+str(MAX_TEXT_FIELD_LEN)+' characters'
    if len(username) == 0:
        errors['username'] = 'Username can\'t be empty'
    elif len(username) > MAX_TEXT_FIELD_LEN:
        errors['username'] = 'Username can\'t be longer than '+str(MAX_TEXT_FIELD_LEN)+' characters'
    if len(first_name) == 0:
        errors['first_name'] = 'First name can\'t be empty'
    elif len(first_name) > MAX_TEXT_FIELD_LEN:
        errors['first_name'] = 'First name can\'t be longer than '+str(MAX_TEXT_FIELD_LEN)+' characters'
    if len(last_name) == 0:
        errors['last_name'] = 'Last name can\'t be empty'
    elif len(last_name) > MAX_TEXT_FIELD_LEN:
        errors['last_name'] = 'Last name can\'t be longer than '+str(MAX_TEXT_FIELD_LEN)+' characters'
    if len(password) < MIN_PASSWORD_LEN:
        errors['password'] = 'Password must be at least '+str(MIN_PASSWORD_LEN)+' characters'

    # Uniqueness validation
    if 'email' not in errors and DBManager.is_email_unique(email) == False:
        errors['email'] = 'Email already exists'
    if 'username' not in errors and DBManager.is_username_unique(username) == False:
        errors['username'] = 'Username already exists'

    # Integrity validation
    if password != password_again:
        errors['password'] = 'Passwords don\'t match'

    if bool(errors) == False:
        tester = {
            'email': email,
            'organization': organization,
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
            'password_hash': generate_password_hash(password)
            }
        insert_id = DBManager.create_tester(tester)

        response = jsonify({'tester_id': insert_id})
        status_code = 201
    else:
        response = jsonify({'errors': errors})
        status_code = 400
        
    return response, status_code


@app.route('/api/get_tester', methods=['GET'])
@is_logged_in
def get_tester():

    # Can't be triggered by normal app use
    if not all(param in request.args for param in ('tester_id', )):
        return jsonify({'errors': {'missing_fields': 'Please supply all required fields'}}), 400

    tester_id = int(request.args.get('tester_id'))

    tester = DBManager.get_tester(tester_id)

    return jsonify({'Tester': tester})


@app.route('/api/get_testers', methods=['GET'])
@is_logged_in
def get_testers():
    testers = DBManager.get_testers()
    return jsonify({"Testers": testers})


@app.route('/api/get_tester_usernames', methods=['GET'])
@is_logged_in
def get_tester_usernames():
    return jsonify({"usernames": DBManager.get_tester_usernames()})


@app.route('/api/search_testers', methods=['GET'])
@is_logged_in
def search_testers():

    # Can't be triggered by normal app use
    if not all(param in request.args for param in ('query', )):
        return jsonify({'errors': {'missing_fields': 'Please supply all required fields'}}), 400

    query = request.args.get('query')

    testers = DBManager.search_testers(query)

    return jsonify({"Testers": testers})


#-----------
# Utilities
#-----------


def generate_session_id():
    random_string = os.urandom(30)
    epoch_time = str(int(time.time()))
    return hashlib.sha1(random_string + epoch_time)


def random_word(length):
    return ''.join(random.choice(string.lowercase) for i in range(length))


def generate_image_from_string(img_string, patient_id, date):
    img_data = base64.b64decode(img_string)
    save_path = '/var/www/ucap-backend/ucap/static/test_images/'
    filename = str(patient_id)+'_'+str(date)+'_'+random_word(8)+'.jpg'
    filepath = os.path.join(save_path, filename)
    with open(filepath, 'wb') as f:
        f.write(img_data)
    return filename


# Should handle leap years and should not hardcode the valid year range (very low priority)
def is_valid_dob(dob):
    if len(dob) != 10:
        return False
    if int(dob[:4]) < 1900 or int(dob[:4]) > 2016:
        return False
    if int(dob[5:7]) < 1 or int(dob[5:7]) > 12:
        return False
    if int(dob[8:]) < 1 or int(dob[8:]) > 31:
        return False
    return True


#-----------------
# Post-processors
#-----------------

def cdt_post_process(test):

    test['details']['result_image_link'] = generate_image_from_string(test['details']['result_image'], test['patient_id'], test['test_date'])

    score_breakdown = json.loads(test['details']['score_breakdown'])
    for key, value in score_breakdown.iteritems():
        test['details'][key] = value
    del test['details']['score_breakdown']


if __name__ == '__main__':
    app.run()
