#!/home/ubuntu/ucap/ucap_venv/bin/python
from ucap import app
from flask import g
import sqlite3, sys
dbPath = '/home/ubuntu/ucap/ucap_database.db'


def connect_db():
    return sqlite3.connect(dbPath)


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = connect_db()
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()
        

def create_test(test):
    insert_id = None
    curs = get_db().cursor()
    curs.execute(   "INSERT INTO " + \
                    "tests (app, patient_id, tester_id, test_date) " + \
                    "VALUES (?, ?, ?, ?)", 
                    (test['app'], test['patient_id'], test['tester_id'], test['test_date']))
    get_db().commit()
    insert_id = curs.lastrowid
    curs.execute(   "INSERT INTO " + \
                    test['app']+"_tests ("+', '.join(test['details'].keys())+", test_id) " + \
                    "VALUES ("+', '.join(list('?'*len(test['details'].keys())))+", ?)", # make a string of question marks
                    tuple(test['details'].values()+[insert_id]))
    get_db().commit()
    return insert_id


def get_tests(app_code, query=None):

    tests = []
    curs = get_db().cursor()

    if query != None:
        join_str =  "INNER JOIN testers ON testers.id = tests.tester_id " + \
                    "INNER JOIN patients ON patients.id = tests.patient_id "
        condition_str =     " WHERE patients.visible_patient_id LIKE ? OR " + \
                                    "patients.patient_group LIKE ? OR " + \
                                    "patients.name LIKE ? OR " + \
                                    "testers.organization LIKE ? OR " + \
                                    "testers.username LIKE ? OR " + \
                                    "testers.first_name LIKE ? OR " + \
                                    "testers.last_name LIKE ? OR " + \
                                    "testers.first_name || ' '|| testers.last_name LIKE ?"
        pattern = '%' + query.lower() + '%'
        query_params = [pattern, pattern, pattern, pattern, pattern, pattern, pattern, pattern]
    else:
        join_str = ''
        condition_str = ''
        query_params = []

    if app_code == 'cdt':

        query_str = "SELECT * FROM tests " + \
                    "INNER JOIN cdt_tests ON tests.id = cdt_tests.test_id " + \
                    join_str + \
                    condition_str + ";"

        curs.execute(query_str, tuple(query_params))
        for row in curs:
            tests.append({
                'id': row[0],
                'app': row[1],
                'patient_id': row[2],
                'tester_id': row[3],
                'test_date': row[4],
                # row[5] is id (i.e. the cdt_test-specific id)
                'type': row[6],
                'medium': row[7],
                'elapsed_time': row[8],
                'total': row[9],
                'score1': row[10],
                'score2': row[11],
                'score3': row[12],
                'score4': row[13],
                'score5': row[14],
                'result_image': row[15],
                'link': row[16]
                })

    elif app_code == 'star':

        query_str = "SELECT * FROM tests " + \
                    "INNER JOIN star_tests ON tests.id = star_tests.test_id " + \
                    join_str + \
                    condition_str + ";"

        curs.execute(query_str, tuple(query_params))
        for row in curs:
            tests.append({
                'id': row[0],
                'app': row[1],
                'patient_id': row[2],
                'tester_id': row[3],
                'test_date': row[4],
                # row[5] is id (i.e. the cdt_test-specific id)
                'elapsed_time': row[6],
                'score_total': row[7],
                'score_expected': row[8],
                'score_zones': row[9],
                'perseverations': row[10],
                'latency_average': row[11],
                'latency_sd': row[12],
                'events': row[13]
                })

    elif app_code == 'mole':

        query_str = "SELECT * FROM tests " + \
                    "INNER JOIN mole_tests ON tests.id = mole_tests.test_id " + \
                    join_str + \
                    condition_str + ";"

        curs.execute(query_str, tuple(query_params))
        for row in curs:
            tests.append({
                'id': row[0],
                'app': row[1],
                'patient_id': row[2],
                'tester_id': row[3],
                'test_date': row[4],
                # row[5] is id (i.e. the cdt_test-specific id)
                'target_visibility': row[6],
                'target_latency': row[7],
                'level_duration': row[8],
                'level_progression': row[9],
                'hit_sound': row[10],
                'hit_vibration': row[11],
                'avg_reaction_time': row[12],
                'reaction_time_sd': row[13],
                'events': row[14],
                'avg_reaction_times_by_level': row[15],
                'reaction_time_sds_by_level': row[16],
                'moles_hit_by_level': row[17],
                'moles_missed_by_level': row[18],
                'bunnies_hit_by_level': row[19],
                'bunnies_missed_by_level': row[20]
                })

    return tests 
        

# Patients

def create_patient(patient):
    insert_id = None
    curs = get_db().cursor()
    curs.execute(   "INSERT INTO patients (patient_type, visible_patient_id, patient_group, name, dob, notes, gender, password_hash) " + \
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?);", 
                    (   patient['patient_type'], patient['visible_patient_id'], patient['group'], patient['name'], 
                        patient['dob'], patient['notes'], patient['gender'],patient['password_hash']))
    get_db().commit()
    insert_id = curs.lastrowid
    return insert_id


def get_patient(patient_id, tester_id):
    # TODO: Mask the name if tester user_id doesn't have permission to see it
    patient = None
    curs = get_db().cursor()
    curs.execute("SELECT * FROM patients WHERE id = ?;", (patient_id,))
    row = curs.fetchone()
    if row != None:
        patient = process_patient(row, tester_id, curs)
    return patient


def get_patients(tester_id, patient_type, test_selection):
    patients = []
    curs = get_db().cursor()

    condition_str = ""
    query_params = []

    if patient_type != None:
        condition_str += " WHERE patients.patient_type = ?"
        query_params.append(patient_type)

    query_str = "SELECT DISTINCT patients.* FROM patients "+condition_str+";"

    rows = []
    curs.execute(query_str, tuple(query_params))
    for row in curs: # to prevent conflict when curs is called in the next for loop
        rows.append(row)

    for row in rows:
        patient = process_patient(row, tester_id, curs, test_selection)
        if patient != None:
            patients.append(patient)

    return patients 


def get_visible_patient_id(patient_id):
    curs = get_db().cursor()
    curs.execute("SELECT visible_patient_id FROM patients WHERE id = ?;", (patient_id,))
    row = curs.fetchone()
    if row != None:
        visible_patient_id = row[0]
    return visible_patient_id


def get_visible_patient_ids():
    visible_patient_ids = []
    curs = get_db().cursor()
    curs.execute("SELECT visible_patient_id FROM patients;")
    for row in curs:
        visible_patient_ids.append(row[0])
    return visible_patient_ids 


def is_patient_blind(patient_id):
    is_blind = False
    curs = get_db().cursor()
    curs.execute("SELECT patient_type FROM patients WHERE id = ?;", (patient_id,))
    row = curs.fetchone()
    if row != None:
        is_blind = row[0] == 'blind'
    return is_blind


def get_patient_password_hash(patient_id):
    password_hash = None
    curs = get_db().cursor()
    curs.execute("SELECT password_hash FROM patients WHERE id = ?;", (patient_id,))
    row = curs.fetchone()
    if row != None:
        password_hash = row[0]
    return password_hash


def unlock_patient(user_id, patient_id):
    insert_id = None
    curs = get_db().cursor()
    curs.execute("INSERT INTO patient_visibility (patient_id, tester_id) VALUES (?, ?)", (patient_id, user_id))
    get_db().commit()
    insert_id = curs.lastrowid
    return insert_id


def search_patients(tester_id, query, test_selection):

    patients = []
    
    query = query.lower()
    pattern = '%' + query + '%'

    curs = get_db().cursor()

    rows = []
    curs.execute(   "SELECT DISTINCT patients.* FROM patients " + \
                    "LEFT JOIN tests ON tests.patient_id = patients.id " + \
                    "LEFT JOIN testers ON testers.id = tests.tester_id WHERE " + \
                    "patients.patient_type LIKE ? OR " + \
                    "patients.visible_patient_id LIKE ? OR " + \
                    "patients.patient_group LIKE ? OR " + \
                    "patients.name LIKE ? OR " + \
                    "patients.notes LIKE ? OR " + \
                    "patients.gender LIKE ? OR " + \
                    "testers.organization LIKE ? OR " + \
                    "testers.username LIKE ? OR " + \
                    "testers.first_name LIKE ? OR " + \
                    "testers.last_name LIKE ? OR " + \
                    "testers.first_name || ' '|| testers.last_name LIKE ?;", 
                (pattern, pattern, pattern, pattern, pattern, pattern, pattern, pattern, pattern, pattern, pattern))
    for row in curs: # to prevent conflict when curs is called in the next for loop
        rows.append(row)

    for row in rows:
        patient = process_patient(row, tester_id, curs, test_selection)
        if patient != None:
            patients.append(patient)

    return patients      


# Testers

def create_tester(tester):
    insert_id = None
    curs = get_db().cursor()
    curs.execute(   "INSERT INTO testers (active, email, organization, username, first_name, last_name, password_hash, is_admin) " + \
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                    (1, tester['email'], tester['organization'], tester['username'], tester['first_name'], tester['last_name'], tester['password_hash'], 0))
    get_db().commit()
    insert_id = curs.lastrowid
    return insert_id


def get_tester(tester_id):
    tester = None
    curs = get_db().cursor()
    curs.execute("SELECT organization, username, first_name, last_name FROM testers WHERE id = ? AND active = 1;", (tester_id,))
    row = curs.fetchone()
    if row != None:
        tester = {
            'organization': row[0],
            'username': row[1],
            'first_name': row[2],
            'last_name': row[3]
        }
    return tester


def get_testers():
    testers = []
    curs = get_db().cursor()

    curs.execute("SELECT DISTINCT organization, username, first_name, last_name " + \
                    "FROM testers " + \
                    "WHERE testers.active = 1;")
    for row in curs:
        testers.append({
            'organization': row[0],
            'username': row[1],
            'first_name': row[2],
            'last_name': row[3]
        })
  
    return testers


def get_logged_in_tester_id(session_id):
    tester_id = None
    curs = get_db().cursor()
    curs.execute("SELECT tester_id FROM sessions WHERE id = ?;", (session_id,))
    row = curs.fetchone()
    if row != None:
        tester_id = row[0]
    return tester_id


def is_tester_active(username):
    is_active = False
    curs = get_db().cursor()
    curs.execute("SELECT active FROM testers WHERE username = ?;", (username,))
    row = curs.fetchone()
    if row != None:
        is_active = row[0] == 1
    return is_active


def get_tester_usernames():
    usernames = []
    curs = get_db().cursor()
    curs.execute("SELECT username FROM testers WHERE active = 1;")
    for row in curs:
        usernames.append(row[0])
    return usernames


def get_tester_password_hash(username):
    password_hash = None
    curs = get_db().cursor()
    curs.execute("SELECT password_hash FROM testers WHERE username = ?;", (username,))
    row = curs.fetchone()
    if row != None:
        password_hash = row[0]
    return password_hash


def search_testers(query):

    testers = []
    
    query = query.lower()
    pattern = '%' + query + '%'

    curs = get_db().cursor()

    rows = []
    curs.execute(   "SELECT DISTINCT testers.organization, testers.username, testers.first_name, testers.last_name FROM testers " + \
                    "LEFT JOIN tests ON tests.tester_id = testers.id " + \
                    "LEFT JOIN patients ON patients.id = tests.patient_id WHERE " + \
                    "testers.active = 1 AND (" + \
                    "testers.organization LIKE ? OR " + \
                    "testers.username LIKE ? OR " + \
                    "testers.first_name LIKE ? OR " + \
                    "testers.last_name LIKE ? OR " + \
                    "testers.first_name || ' ' || testers.last_name LIKE ? OR " + \
                    "patients.visible_patient_id LIKE ? OR " + \
                    "patients.name LIKE ?);", 
                (pattern, pattern, pattern, pattern, pattern, pattern, pattern))
    for row in curs:
        testers.append({
            'organization': row[0],
            'username': row[1],
            'first_name': row[2],
            'last_name': row[3]
        })
  
    return testers 


# Sessions

def create_session(session_id, username):
    insert_id = None
    curs = get_db().cursor()
    curs.execute("SELECT id FROM testers WHERE username = ?", (username,))
    row = curs.fetchone()
    if row != None:
        tester_id = row[0]
        curs.execute("INSERT INTO sessions VALUES (?, ?);", (session_id, tester_id))
        insert_id = curs.lastrowid
        get_db().commit()
    return insert_id        


def check_session(session_id):
    count = 0
    curs = get_db().cursor()
    curs.execute("SELECT COUNT(*) as count FROM sessions WHERE id = ?;", (session_id,))
    row = curs.fetchone()
    count = row[0]
    return count


def delete_session(session_id):
    curs = get_db().cursor()
    curs.execute("DELETE FROM sessions WHERE id = ?;", (session_id,))
    get_db().commit()


# Validation

def is_visible_patient_id_unique(visible_patient_id):
    is_unique = False
    curs = get_db().cursor()
    curs.execute("SELECT COUNT(*) as count FROM patients WHERE visible_patient_id = ?;", (visible_patient_id,))
    row = curs.fetchone()
    is_unique = row[0] == 0
    return is_unique


def is_email_unique(email):
    is_unique = False
    curs = get_db().cursor()
    curs.execute("SELECT COUNT(*) as count FROM testers WHERE email = ? COLLATE NOCASE;", (email,))
    row = curs.fetchone()
    is_unique = row[0] == 0
    return is_unique


def is_username_unique(username):
    is_unique = False
    curs = get_db().cursor()
    curs.execute("SELECT COUNT(*) as count FROM testers WHERE username = ? COLLATE NOCASE;", (username,))
    row = curs.fetchone()
    is_unique = row[0] == 0
    return is_unique


# Helpers

def process_patient(row, tester_id, curs, test_selection=False):

    patient = {
        'id': row[0],
        'patient_type': row[1],
        'visible_patient_id': row[2],
        'group': row[3],
        'name': row[4],
        'dob': row[5],
        'notes': row[6],
        'gender': row[7],
        'is_visible': True
    }

    # Make empty values more meaningful
    patient = {key: ("N/A" if value == "" else value) for (key, value) in patient.iteritems()}

    # If the requesting user doesn't have the right to see this patient's information,
    # the information is redacted, except the patient ID and whether or not they're blind
    # This doesn't apply to admins or anonymous patients
    curs.execute("SELECT COUNT(*) as count FROM patient_visibility WHERE patient_id = ? AND tester_id = ?", (patient['id'], tester_id))
    count = curs.fetchone()[0]
    if not is_admin(tester_id) and patient['patient_type'] != 'anonymous':
        if count < 1:
            patient['group'] = '******'
            patient['name'] = '******'
            patient['dob'] = '******'
            patient['notes'] = '******'
            patient['gender'] = '******'
            patient['is_visible'] = False

    # If the requesting user is testing a patient and the patient is a blind patient they've created, the patient should
    # not appear in the list of testable patients. Since admins can see all patients, they can't test
    # blind patients
    if test_selection == True and (count == 1 or is_admin(tester_id)) and patient['patient_type'] == 'blind':
        return None
    
    return patient

def is_admin(tester_id):
    is_admin = False
    curs = get_db().cursor()
    curs.execute("SELECT is_admin FROM testers WHERE id = ?;", (tester_id,))
    row = curs.fetchone()
    if row != None:
        is_admin = row[0] == 1
    return is_admin    
