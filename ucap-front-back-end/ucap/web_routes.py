#!/home/ubuntu/ucap/ucap_venv/bin/python
from ucap import app
from flask import jsonify, abort, make_response, request, g, render_template, redirect, url_for, Response
import json
from functools import wraps
import urllib, urllib2
import datetime
from cookielib import CookieJar
import api

SERVER_URL = 'http://162.246.156.143'

CDT_TEST_HEADERS = ['ID', 'Date', 'Tester', 'Patient', 'Medium', 'Elapsed Time (sec)', 'Subscore 1', 'Subscore 2', 'Subscore 3', 'Subscore 4', 'Subscore 5', 'Total Score']
CDT_TEST_KEYS = ['id', 'test_date', 'tester', 'visible_patient_id', 'medium', 'elapsed_time', 'score1', 'score2', 'score3', 'score4', 'score5', 'total']
STAR_TEST_HEADERS = ['ID', 'Date', 'Tester', 'Patient', 'Elapsed Time (sec)', 'Score', 'Score Zones', 'Perseverations', 'Latency Average (sec)', 'Latency S.D. (sec)', 'Events']
STAR_TEST_KEYS = ['id', 'test_date', 'tester', 'visible_patient_id', 'elapsed_time', 'score', 'score_zones', 'perseverations', 'latency_average', 'latency_sd', 'events']
MOLE_TEST_HEADERS = ['ID', 'Date', 'Tester', 'Patient', 'Target Visibility (sec)', 'Target Latency (sec)', 'Level Duration (sec)', 'Level Progression (%)', 'Hit Sound', 'Hit Vibration', 'Avg. Reaction Time (sec)', 'Reaction Time S.D. (sec)', 'Events']
MOLE_TEST_KEYS = ['id', 'test_date', 'tester', 'visible_patient_id', 'target_visibility', 'target_latency', 'level_duration', 'level_progression', 'hit_sound', 'hit_vibration', 'avg_reaction_time', 'reaction_time_sd', 'events']
PATIENT_HEADERS = ['Patient ID', 'Name', 'Type', 'Group', 'Gender', 'Date of Birth', 'Notes']
PATIENT_KEYS = ['visible_patient_id', 'name', 'patient_type', 'group', 'gender', 'dob', 'notes']
TESTER_HEADERS = ['Organization', 'Username', 'First Fame', 'Last Name']
TESTER_KEYS = ['organization', 'username', 'first_name', 'last_name']


#------
# Main
#------

@app.route('/')
@app.route('/<success>')
def web_index_page(success=False):

    # Forward the request to the API
    url = SERVER_URL+'/api/check_session'
    req = urllib2.Request(url, json.dumps({}))
    if 'sessionID' in request.cookies:
        req.add_header('Cookie', 'sessionID='+request.cookies['sessionID'])
    req.add_header('Content-Type', 'application/json')
    # Logging out will never fail with an HTTPError
    rsp = urllib2.urlopen(req)

    return render_template('main.html') if json.loads(rsp.read())['is_logged_in'] else render_template('index.html', success=success)


@app.route('/main')
def web_main_page():
    return render_template('main.html')


#------------
#  Sessions
#------------

@app.route('/api/web/login', methods=['POST'])
def web_login():

    params = multi_dict_to_dict(request.form)

    params = json.dumps(params, ensure_ascii=False)

    # Forward the request to the API
    url = SERVER_URL+'/api/login'
    req = urllib2.Request(url, params)
    req.add_header('Content-Type', 'application/json')
    try: # Relies on urllib2 returning an exception if the response code from urllib2 indicates "something bad happened"
        rsp = urllib2.urlopen(req)

        cookie_jar = CookieJar()
        session_id_str = cookie_jar.make_cookies(rsp, req)[0].value

        response = make_response(redirect(url_for('web_main_page')))
        response.set_cookie('sessionID', session_id_str)
        return response
    except urllib2.HTTPError, error:
        return render_template('index.html',    errors=json.loads(error.read())['errors'], 
                                                username=request.form['username'])
        

@app.route('/logout', methods=['GET', 'POST'])
def web_logout():

    # Forward the request to the API
    url = SERVER_URL+'/api/logout'
    req = urllib2.Request(url, json.dumps({}))
    if 'sessionID' in request.cookies:
        req.add_header('Cookie', 'sessionID='+request.cookies['sessionID'])
    req.add_header('Content-Type', 'application/json')
    # Logging out will never fail with an HTTPError
    urllib2.urlopen(req)
    return redirect(url_for('web_index_page'))


#--------
## Tests
#--------

@app.route('/choose_test', methods=['GET'])
def web_choose_test_page():
    return render_template('choose_test.html')   

@app.route('/tests', methods=['GET'])
def web_get_tests():

    params = multi_dict_to_dict(request.args)

    # Forward the request to the API
    url = SERVER_URL+'/api/get_tests?'+urllib.urlencode(params)
    req = urllib2.Request(url)
    req.add_header('Content-Type', 'application/json')
    if 'sessionID' in request.cookies:
        req.add_header('Cookie', 'sessionID='+request.cookies['sessionID'])
    try: # Relies on urllib2 returning an exception if the response code from urllib2 indicates "something bad happened"
        rsp = urllib2.urlopen(req)

        tests = json.loads(rsp.read())['Tests']

        if 'csv' in request.args and request.args.get('csv') == 'true':

            for test in tests:
                test['tester'] = test['tester_first_name'] + ' ' + test['tester_last_name'] + ' (' + test['tester_username'] + ')'
                if request.args.get('app_code') == 'star':
                    test['score'] = str(test['score_total']) + '/' + str(test['score_expected'])

            if request.args.get('app_code') == 'cdt':
                response = Response(make_csv_str(CDT_TEST_HEADERS, CDT_TEST_KEYS, tests), mimetype='text/csv')
            elif request.args.get('app_code') == 'star':
                response = Response(make_csv_str(STAR_TEST_HEADERS, STAR_TEST_KEYS, tests), mimetype='text/csv')
            elif request.args.get('app_code') == 'mole':
                (EXTENDED_MOLE_TEST_HEADERS, EXTENDED_MOLE_TEST_KEYS) = extend_wam_csv_headers_and_keys(MOLE_TEST_HEADERS, MOLE_TEST_KEYS, tests)
                process_wam_tests(tests)
                response = Response(make_csv_str(EXTENDED_MOLE_TEST_HEADERS, EXTENDED_MOLE_TEST_KEYS, tests), mimetype='text/csv')

            filename = 'test_results'
            response.headers['Content-Disposition'] = 'attachment; filename={0}.csv'.format(filename)
            return response

        else:

            return render_template('tests.html', tests=tests)

    except urllib2.HTTPError, error:
        abort(401)


@app.route('/api/web/search_tests', methods=['GET'])
def web_search_tests():

    params = multi_dict_to_dict(request.args)

    # Forward the request to the API
    url = SERVER_URL+'/api/get_tests?'+urllib.urlencode(params)
    req = urllib2.Request(url)
    req.add_header('Content-Type', 'application/json')
    if 'sessionID' in request.cookies:
        req.add_header('Cookie', 'sessionID='+request.cookies['sessionID'])
    try: # Relies on urllib2 returning an exception if the response code from urllib2 indicates "something bad happened"
        rsp = urllib2.urlopen(req)

        tests = json.loads(rsp.read())['Tests']

        if 'csv' in request.args and request.args.get('csv') == 'true':
            response = Response(make_csv_str(TESTER_HEADERS, TESTER_KEYS, testers), mimetype='text/csv')
            filename = 'test_results'
            response.headers['Content-Disposition'] = 'attachment; filename={0}.csv'.format(filename)
            return response
        else:
            return render_template('tests.html', tests=tests)

    except urllib2.HTTPError, error:
        abort(401)


#-----------
## Patients
#-----------

@app.route('/create_patient')
def web_create_patient_page():
    return render_template('create_patient.html')


@app.route('/api/web/create_patient', methods=['POST'])
def web_create_patient():

    params = multi_dict_to_dict(request.form)

    # Process params
    if 'month' in params and 'day' in params and 'year' in params:
        dob = datetime.date(int(params['year']), int(params['month']), int(params['day']))
        params['dob'] = dob.strftime('%Y-%m-%d')
        for key in ('year', 'month', 'day'):
            del params[key]
    else:
        params['dob'] = ''

    params = json.dumps(params, ensure_ascii=False)

    # Forward the request to the API
    url = SERVER_URL+'/api/create_patient'
    req = urllib2.Request(url, params)
    req.add_header('Content-Type', 'application/json')
    if 'sessionID' in request.cookies:
        req.add_header('Cookie', 'sessionID='+request.cookies['sessionID'])
    try: # Relies on urllib2 returning an exception if the response code from urllib2 indicates "something bad happened"
        rsp = urllib2.urlopen(req)
        try:
            password = json.loads(rsp.read())['password']
            return make_response(redirect(url_for('web_get_patients',   success='patient_creation_successful',
                                                                        visible_patient_id=request.form['visible_patient_id'],
                                                                        password=password )))
        except KeyError, ValueError:
            return make_response(redirect(url_for('web_get_patients',   success='patient_creation_successful',
                                                                        visible_patient_id=request.form['visible_patient_id'] )))           
    except urllib2.HTTPError, error:
        return render_template('create_patient.html',   errors=json.loads(error.read())['errors'],   
                                                        visible_patient_id=request.form['visible_patient_id'], 
                                                        patient_type=request.form['patient_type'] if 'patient_type' in request.form else '', 
                                                        group=request.form['group'], 
                                                        name=request.form['name'], 
                                                        gender=request.form['gender'] if 'gender' in request.form else '', 
                                                        month=request.form['month'] if 'month' in request.form else '', 
                                                        day=request.form['day'] if 'day' in request.form else '', 
                                                        year=request.form['year'] if 'year' in request.form else '', 
                                                        notes=request.form['notes'])


@app.route('/patients', methods=['GET'])
@app.route('/patients/<success>')
def web_get_patients(success=False):

    params = multi_dict_to_dict(request.args)

    params['test_selection'] = 0

    # Forward the request to the API
    url = SERVER_URL+'/api/get_patients?'+urllib.urlencode(params)
    req = urllib2.Request(url)
    req.add_header('Content-Type', 'application/json')
    if 'sessionID' in request.cookies:
        req.add_header('Cookie', 'sessionID='+request.cookies['sessionID'])
    try: # Relies on urllib2 returning an exception if the response code from urllib2 indicates "something bad happened"
        rsp = urllib2.urlopen(req)

        patients = json.loads(rsp.read())['Patients']

        if 'csv' in request.args and request.args.get('csv') == 'true':
            response = Response(make_csv_str(PATIENT_HEADERS, PATIENT_KEYS, patients), mimetype='text/csv')
            filename = 'patients'
            response.headers['Content-Disposition'] = 'attachment; filename={0}.csv'.format(filename)
            return response
        else:
            return render_template('patients.html',     patients=patients,
                                                        success=success, 
                                                        visible_patient_id=request.args['visible_patient_id'] if 'visible_patient_id' in request.args else None, 
                                                        password=request.args['password'] if 'password' in request.args else None)

    except urllib2.HTTPError, error:
        abort(401)


@app.route('/api/web/search_patients', methods=['GET'])
def web_search_patients():

    params = multi_dict_to_dict(request.args)

    # Forward the request to the API
    url = SERVER_URL+'/api/search_patients?'+urllib.urlencode(params)
    req = urllib2.Request(url)
    req.add_header('Content-Type', 'application/json')
    if 'sessionID' in request.cookies:
        req.add_header('Cookie', 'sessionID='+request.cookies['sessionID'])
    try: # Relies on urllib2 returning an exception if the response code from urllib2 indicates "something bad happened"
        rsp = urllib2.urlopen(req)

        patients = json.loads(rsp.read())['Patients']

        if 'csv' in request.args and request.args.get('csv') == 'true':
            response = Response(make_csv_str(PATIENT_HEADERS, PATIENT_KEYS, patients), mimetype='text/csv')
            filename = 'patients'
            response.headers['Content-Disposition'] = 'attachment; filename={0}.csv'.format(filename)
            return response
        else:
            return render_template('patients.html',     patients=patients,
                                                        visible_patient_id=request.args['visible_patient_id'] if 'visible_patient_id' in request.args else None, 
                                                        password=request.args['password'] if 'password' in request.args else None)

    except urllib2.HTTPError, error:
        abort(401)


#----------
## Testers
#----------


@app.route('/api/web/register', methods=['POST'])
def web_create_tester():

    params = multi_dict_to_dict(request.form)

    params = json.dumps(params, ensure_ascii=False)

    # Forward the request to the API
    url = SERVER_URL+'/api/create_tester'
    req = urllib2.Request(url, params)
    req.add_header('Content-Type', 'application/json')
    if 'sessionID' in request.cookies:
        req.add_header('Cookie', 'sessionID='+request.cookies['sessionID'])    
    try: # Relies on urllib2 returning an exception if the response code from urllib2 indicates "something bad happened"
        urllib2.urlopen(req)
        return make_response(redirect(url_for('web_index_page', success='registration_successful')))
    except urllib2.HTTPError, error:
        return render_template('index.html',        errors=json.loads(error.read())['errors'], 
                                                    email=request.form['email'],
                                                    organization=request.form['organization'],  
                                                    username=request.form['username'], 
                                                    first_name=request.form['first_name'],
                                                    last_name=request.form['last_name'])


@app.route('/testers', methods=['GET'])
def web_get_testers():

    params = multi_dict_to_dict(request.args)

    # Forward the request to the API
    url = SERVER_URL+'/api/get_testers?'+urllib.urlencode(params)
    req = urllib2.Request(url)
    req.add_header('Content-Type', 'application/json')
    if 'sessionID' in request.cookies:
        req.add_header('Cookie', 'sessionID='+request.cookies['sessionID'])
    try: # Relies on urllib2 returning an exception if the response code from urllib2 indicates "something bad happened"
        rsp = urllib2.urlopen(req)

        testers = json.loads(rsp.read())['Testers']

        if 'csv' in request.args and request.args.get('csv') == 'true':
            response = Response(make_csv_str(TESTER_HEADERS, TESTER_KEYS, testers), mimetype='text/csv')
            filename = 'testers'
            response.headers['Content-Disposition'] = 'attachment; filename={0}.csv'.format(filename)
            return response
        else:
            return render_template('testers.html', testers=testers)

    except urllib2.HTTPError, error:
        abort(401)


@app.route('/api/web/search_testers', methods=['GET'])
def web_search_testers():

    params = multi_dict_to_dict(request.args)

    # Forward the request to the API
    url = SERVER_URL+'/api/search_testers?'+urllib.urlencode(params)
    req = urllib2.Request(url)
    req.add_header('Content-Type', 'application/json')
    if 'sessionID' in request.cookies:
        req.add_header('Cookie', 'sessionID='+request.cookies['sessionID'])
    try: # Relies on urllib2 returning an exception if the response code from urllib2 indicates "something bad happened"
        rsp = urllib2.urlopen(req)

        testers = json.loads(rsp.read())['Testers']

        if 'csv' in request.args and request.args.get('csv') == 'true':
            response = Response(make_csv_str(TESTER_HEADERS, TESTER_KEYS, testers), mimetype='text/csv')
            filename = 'testers'
            response.headers['Content-Disposition'] = 'attachment; filename={0}.csv'.format(filename)
            return response
        else:
            return render_template('testers.html', testers=testers)

    except urllib2.HTTPError, error:
        abort(401)


#-----------
# Utilities
#-----------

# Converts a Flask MultiDict to a regular Python dictionary
# Useful if the MultiDict is an ImmutableMultiDict
# Assumes that the MultiDict's "multi" capabilities aren't being used
def multi_dict_to_dict(multi_dict):
    dictionary = {}
    for key, value in multi_dict.iteritems():
        dictionary[key] = value
    return dictionary


def make_csv_str(headers, keys, items):
    csv_as_list = []
    csv_as_list.append('\t'.join(headers))
    for item in items:
        filtered_item = [str(item[key]) for key in keys]
        csv_as_list.append('\t'.join(filtered_item))
    return '\n'.join(csv_as_list)


def extend_wam_csv_headers_and_keys(headers, keys, tests):

    EXTENDED_MOLE_TEST_HEADERS = MOLE_TEST_HEADERS[:]
    EXTENDED_MOLE_TEST_KEYS = MOLE_TEST_KEYS[:]

    if len(tests) > 0:
        for level in xrange(len(json.loads(tests[0]['moles_hit_by_level']))):

            EXTENDED_MOLE_TEST_HEADERS.append("Avg. Reaction Time (sec) - L"+str(level+1))
            EXTENDED_MOLE_TEST_KEYS.append('avg_reaction_time_'+str(level+1))

            EXTENDED_MOLE_TEST_HEADERS.append("Reaction Time S.D. (sec) - L"+str(level+1))
            EXTENDED_MOLE_TEST_KEYS.append('reaction_time_sd_'+str(level+1))
            
            EXTENDED_MOLE_TEST_HEADERS.append("Moles Hit - L"+str(level+1))
            EXTENDED_MOLE_TEST_KEYS.append('moles_hit_'+str(level+1))

            EXTENDED_MOLE_TEST_HEADERS.append("Moles Missed - L"+str(level+1))
            EXTENDED_MOLE_TEST_KEYS.append('moles_missed_'+str(level+1))
            
            EXTENDED_MOLE_TEST_HEADERS.append("Bunnies Hit - L"+str(level+1))
            EXTENDED_MOLE_TEST_KEYS.append('bunnies_hit_'+str(level+1))
            
            EXTENDED_MOLE_TEST_HEADERS.append("Bunnies Missed - L"+str(level+1))
            EXTENDED_MOLE_TEST_KEYS.append('bunnies_missed_'+str(level+1))

    return (EXTENDED_MOLE_TEST_HEADERS, EXTENDED_MOLE_TEST_KEYS)


def process_wam_tests(tests):
    for test in tests:
        test['target_visibility'] = test['target_visibility']/float(1000)
        test['target_latency'] = test['target_latency']/float(1000)
        test['level_duration'] = test['level_duration']/float(1000)
        test['level_progression'] = test['level_progression']*float(100)
        test['hit_sound'] = 'On' if test['hit_sound'] == 1 else 'Off'
        test['hit_vibration'] = 'On' if test['hit_vibration'] == 1 else 'Off'
        test['avg_reaction_time'] = test['avg_reaction_time']/float(1000)
        test['reaction_time_sd'] = test['reaction_time_sd']/float(1000)
        for level in xrange(len(json.loads(test['moles_hit_by_level']))):
            test['avg_reaction_time_'+str(level+1)] = json.loads(test['avg_reaction_times_by_level'])[level]/float(1000)
            test['reaction_time_sd_'+str(level+1)] = json.loads(test['reaction_time_sds_by_level'])[level]/float(1000)
            test['moles_hit_'+str(level+1)] = json.loads(test['moles_hit_by_level'])[level]
            test['moles_missed_'+str(level+1)] = json.loads(test['moles_missed_by_level'])[level]
            test['bunnies_hit_'+str(level+1)] = json.loads(test['bunnies_hit_by_level'])[level]
            test['bunnies_missed_'+str(level+1)] = json.loads(test['bunnies_missed_by_level'])[level]
        del test['avg_reaction_times_by_level']
        del test['reaction_time_sds_by_level']
        del test['moles_hit_by_level']
        del test['moles_missed_by_level']
        del test['bunnies_hit_by_level']
        del test['bunnies_missed_by_level']