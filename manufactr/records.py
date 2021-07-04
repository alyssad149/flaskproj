from flask import(
    Blueprint, flash, g, redirect, render_template, request, url_for, session
)
from werkzeug.exceptions import abort
from markupsafe import Markup, escape

from manufactr.auth import login_required
from manufactr.db import get_db

import copy

bp = Blueprint('records', __name__, url_prefix='/records')


@bp.route('/')
@login_required
def index():
    role = g.user['role']
    if(role == "Manager"):
        db = get_db()
        dnames = db.execute('''SELECT department_name
                                FROM department_names''').fetchall()
        return redirect(url_for('records.display'))
    else:
        return render_template('records/index.html')


@bp.route('/display', methods=('GET', 'POST'))
@login_required
def display():
    db = get_db()
    if(g.user['role'] != "GroupLead"):
        dnames = db.execute('''SELECT department_name
                                FROM department_names;''').fetchall()
    else:
        dnames = db.execute('''SELECT department FROM group_lead_department
                                WHERE id = ?;''', (g.user['id'],)).fetchall()

    if request.method == 'POST':
        startdate = request.form['startdate']
        enddate = request.form['enddate']
        checkedDepartment = []
        for (d,) in dnames:
            checkedDepartment.append(request.form.get(d))

        error = None

        if not startdate:
            error = 'Start date is required.'

        if not enddate:
            error = 'End date is required.'

        if error is not None:
            flash(error)

        return redirect(url_for('records.resultsDisplay', startdate=startdate, enddate=enddate, checkedDepartment=checkedDepartment))

    return render_template('records/display.html', dnames=dnames)


@bp.route('/results_display')
@login_required
def resultsDisplay():
    startdate = request.args.get('startdate')
    enddate = request.args.get('enddate')
    checkedDepartment = request.args.getlist('checkedDepartment')

    db = get_db()
    combinedList = map(lambda x: (startdate, enddate, x), checkedDepartment)
    # housekeeping
    (tempExist,) = db.execute('''SELECT COUNT(name) FROM sqlite_master WHERE type='table' AND name='date_range_id' ''').fetchone()
    if tempExist:
        db.execute('''DROP TABLE date_range_id;''')
    (tempExist,) = db.execute('''SELECT COUNT(name) FROM sqlite_master WHERE type='table' AND name='tempdata' ''').fetchone()
    if tempExist:
        db.execute('''DROP TABLE tempdata;''')
    db.execute('''CREATE TABLE date_range_id (id, date, department, units);''')
    db.executemany('''INSERT INTO date_range_id (id, date, department, units)
                        SELECT id, logdate, department, unitcount
                        FROM manufacturinglog
                        WHERE logdate BETWEEN ? AND ?
                        AND department = ?;''', combinedList)
    db.execute("CREATE TABLE tempdata (date, department, units, worker_log_history, worker_count, worker_hours);")
    db.execute('''INSERT INTO tempdata (date, department, units, worker_log_history, worker_count, worker_hours)
                    SELECT date_range_id.date,
                    date_range_id.department,
                    date_range_id.units,
                    manpowerlog.logorder,
                    manpowerlog.manpowercount,
                    manpowerlog.manpowerrate
                    FROM date_range_id
                    LEFT JOIN manpowerlog
                    ON manpowerlog.ddid=date_range_id.id
                    ORDER BY date_range_id.date, date_range_id.department, manpowerlog.logorder;''')
    dateRangeAll = db.execute("SELECT date, department, units, worker_log_history, worker_count, worker_hours FROM tempdata").fetchall()
    dateRangeAllDict = {}
    sendStringTotals = ""
    sendString = ""
    for item in dateRangeAll:
        dictionaryPopulate(item, dateRangeAllDict)

    # range totals
    groupTotals = db.execute('''SELECT tmp.department,
                                dri.unitsum,
                                tmp.tSP
                                FROM (SELECT department,
                                SUM(worker_count * worker_hours) tSP
                                FROM tempdata GROUP BY department) tmp
                                LEFT JOIN
                                (SELECT department, SUM(units) unitsum
                                FROM date_range_id GROUP BY department) dri
                                ON tmp.department = dri.department
                                ''').fetchall()

    for item in groupTotals:
        sendStringTotals += '''<h3>{}</h3>
                                <table>
                                    <tr><th>Units:</th><td>{}</td></tr>
                                    <tr><th>Hours:</th><td>{}</td></tr>
                                </table>'''.format(item[0], item[1], item[2])

    # TODO: tidy up this html
    # daily printouts
    for k in dateRangeAllDict.keys():
        # print(k)
        groupDisplay = ""
        groupDisplay1 = ""
        groupDisplayBody = ""
        groupDisplay2 = ""
        for dk,dv in dateRangeAllDict[k].items():
            # print(dk)
            for unitk in dv.keys():
                # print(unitk)
                # print(dv[unitk])
                totalHourSumProduct = 0
                groupDisplay1 = "<h4>{} Units: {}".format(dk, unitk)
                for workerlogk, workerlogv in dv[unitk].items():
                    # print(workerlogk)
                    # print('distractions' + str(workerlogv['headcount']))
                    rowSumProduct = workerlogv['headcount']*workerlogv['hours']
                    totalHourSumProduct += rowSumProduct
                    htmlstring = "<tr><td>{}</td> <td>{}</td> <td>{}</td></tr>"
                    groupDisplayBody += htmlstring.format(workerlogv['headcount'], workerlogv['hours'], rowSumProduct)
                groupDisplay2 = ''' Hours: {}</h4>
                                    <table>
                                        <tr>
                                            <th>Number of Workers: </th>
                                            <th>Hours per Worker: </th>
                                            <th>Hours: </th>
                                        </tr>
                                        {}
                                    </table>'''.format(totalHourSumProduct, groupDisplayBody)
                groupDisplay += groupDisplay1 + groupDisplay2
                groupDisplay1, groupDisplay2, groupDisplayBody = "", "", ""
        dateDisplay = "<div class='datedisplay'><h3>{}</h3><div class='dategroupdisplay'>{}</div></div>".format(k, groupDisplay)
        sendString += dateDisplay

    return render_template('records/results_display.html', startdate=startdate, enddate=enddate, checkedDepartment=checkedDepartment, sendStringTotals=Markup(sendStringTotals), sendString=Markup(sendString))


def dictionaryPopulate(dataset, dataDict):
    if len(dataset) <= 3:
        dataDict[dataset[0]] = {"headcount": dataset[1], "hours": dataset[2]}
    else:
        if dataset[0] in dataDict.keys():
            dictionaryPopulate(dataset[1:], dataDict[dataset[0]])
        else:
            dataDict[dataset[0]] = {}
            dictionaryPopulate(dataset[1:], dataDict[dataset[0]])




@bp.route('/add', methods=('GET', 'POST'))
@login_required
def add():
    # only pass array of strings
    rnum = ['1']
    db = get_db()
    if(g.user['role'] != "GroupLead"):
        dnames = db.execute('''SELECT department_name
                                FROM department_names;''').fetchall()
    else:
        dnames = db.execute('''SELECT department FROM group_lead_department
                                WHERE id = ?;''', (g.user['id'],)).fetchall()

    if request.method == 'POST':
        date = request.form['addDate']
        department = request.form['addDepartment']
        units = request.form['addUnitCount']
        manpower = request.form['mp1']
        mprates = request.form['mpr1']

        checkExists = db.execute('''SELECT id FROM manufacturinglog
                    WHERE logdate = ? AND department = ?;''', (date, department)).fetchone()

        if checkExists != None:
            flash('Record exists. Please use edit to make changes.')
            return redirect(url_for('records.add'))

        db.execute('''INSERT INTO manufacturinglog (logdate, department, unitcount)
                        VALUES (?, ?, ?);''',
                        (date, department, units))
        db.execute('''INSERT INTO manpowerlog (ddid, manpowercount, manpowerrate)
                        SELECT id, ? AS manpowercount, ? AS manpowerrate
                        FROM manufacturinglog WHERE logdate = ? AND department = ?;''',
                        (manpower, mprates, date, department))
        db.commit()
        return redirect(url_for('records.add', newrnum=rnum))

    return render_template('records/add.html', dnames=dnames, rnum=rnum)

# TODO: see if it's possible to combine this with add
@bp.route('/addWorker', methods=('GET', 'POST'))
def addWorker():
    db = get_db()
    if(g.user['role'] != "GroupLead"):
        dnames = db.execute('''SELECT department_name
                                FROM department_names;''').fetchall()
    else:
        dnames = db.execute('''SELECT department FROM group_lead_department
                                WHERE id = ?;''', (g.user['id'],)).fetchall()

    # rnum is array of strings
    rnum = request.args.getlist('newrnum')
    rnum.append(str(len(rnum)+1))

    if request.method == 'POST':
        date = request.form['addDate']
        department = request.form['addDepartment']
        units = request.form['addUnitCount']

        db.execute('''INSERT INTO manufacturinglog (logdate, department, unitcount)
                        VALUES (?, ?, ?);''',
                        (date, department, units))

        for r in rnum:
            manpower = request.form['mp'+r]
            mprates = request.form['mpr'+r]
            db.execute('''INSERT INTO manpowerlog (ddid, manpowercount, manpowerrate)
                            SELECT id, ? AS manpowercount, ? AS manpowerrate
                            FROM manufacturinglog WHERE logdate = ? AND department = ?''',
                            (manpower, mprates, date, department))
        db.commit()
        return redirect(url_for('records.add', newrnum=['1']))

    return render_template('records/add.html', dnames=dnames, rnum=rnum)


@bp.route('/edit_lookup', methods=('GET', 'POST'))
@login_required
def edit_lookup():
    db = get_db()
    if(g.user['role'] != "GroupLead"):
        dnames = db.execute('''SELECT department_name
                                FROM department_names;''').fetchall()
    else:
        dnames = db.execute('''SELECT department FROM group_lead_department
                                WHERE id = ?;''', (g.user['id'],)).fetchall()

    session['add_wc_field_num'] = []
    session['add_wh_field_num'] = []
    session['first_access_wfield'] = True
    if request.method == 'POST':
        date = request.form['editDate']
        department = request.form['editDepartment']

        checkExists = db.execute('''SELECT id FROM manufacturinglog
                    WHERE logdate = ? AND department = ?;''', (date, department)).fetchone()


        error = None

        if checkExists is None:
            error = 'Record does not exist. Please use add to create a new record.'

        if not date:
            error = 'Date is required.'

        if not department:
            error = 'Department is required.'

        if error is not None:
            flash(error)
            return redirect(url_for('records.edit_lookup'))
        else:
            return redirect(url_for('records.edit', editDate=date, editDepartment=department))

    return render_template('records/edit_lookup.html', dnames=dnames)


@bp.route('/edit', methods=('GET', 'POST'))
@login_required
def edit():
    db = get_db()
    if(g.user['role'] != "GroupLead"):
        dnames = db.execute('''SELECT department_name
                                FROM department_names;''').fetchall()
    else:
        dnames = db.execute('''SELECT department FROM group_lead_department
                                WHERE id = ?;''', (g.user['id'],)).fetchall()

    date = request.args.get('editDate')
    department = request.args.get('editDepartment')
    idUnit = db.execute('''SELECT id, unitcount
                    FROM manufacturinglog
                    WHERE logdate = ? AND department = ?;''',
                    (date, department)).fetchone()

    nworkers = db.execute('''SELECT manpowercount, manpowerrate
                            FROM manpowerlog
                            WHERE ddid = ?
                            ORDER BY logorder''',
                            (idUnit[0],)).fetchall()

    # TODO: see if there's a more efficient way of doing this
    (workerCount, workerHours) = splitToArray(nworkers)
    if (session['first_access_wfield'] and len(session['add_wc_field_num']) == 0):
        session['first_access_wfield'] = False
    else:
        append_item = str(len(session['add_wc_field_num'])+len(workerCount)+1)
        hold_wc = session['add_wc_field_num']
        hold_wc.append(append_item)
        session['add_wc_field_num'] = hold_wc
        hold_wh = session['add_wh_field_num']
        hold_wh.append(append_item)
        session['add_wh_field_num'] = hold_wh

    if request.method == 'POST':
        date = request.args.get('editDate')
        department = request.args.get('editDepartment')
        units = request.form['editUnitCount']
        updateDB = db.execute('''SELECT logorder FROM manpowerlog
                        WHERE ddid = (SELECT id FROM manufacturinglog
                            WHERE logdate=? AND department=?)''',
                            (date, department)).fetchall()
        db.execute('''UPDATE manufacturinglog
                        SET unitcount = ?
                        WHERE logdate = ? AND department = ?;''',
        (units, date, department))
        db.commit()
        for r in range(1, len(workerCount)+1):
            manpower = request.form['mp'+str(r)]
            mprates = request.form['mpr'+str(r)]
            db.execute('''UPDATE manpowerlog
                            SET manpowercount = ?, manpowerrate = ?
                            WHERE logorder = ?;''',
            (manpower, mprates, (updateDB[r-1])[0]))
            db.commit()
        totalLength = range(len(workerCount)+1, len(workerCount) + len(session['add_wc_field_num']))
        for r in totalLength:
            manpower = request.form['mp'+str(r)]
            mprates = request.form['mpr'+str(r)]
            db.execute('''INSERT INTO manpowerlog (ddid, manpowercount, manpowerrate)
                            SELECT id, ? AS manpowercount, ? AS manpowerrate
                            FROM manufacturinglog WHERE logdate = ? AND department = ?''',
                            (manpower, mprates, date, department))
            db.commit()
        error = None

        if not date:
            error = 'Date is required.'

        if not department:
            error = 'Department is required.'

        if error is not None:
            flash(error)
        else:
            return redirect(url_for('records.index'))

    return render_template('records/edit.html',
            dnames=dnames, dateval=date, depval=department, unitval=idUnit[1],
            wcountval=workerCount, whoursval=workerHours)

def splitToArray(originalArray):
    array1 = []
    array2 = []
    for item in originalArray:
        array1.append(item[0])
        array2.append(item[1])
    return (array1, array2)

@bp.route('/resetSession', methods=('GET', 'POST'))
@login_required
def resetSession():
    session['add_wc_field_num'] = []
    session['add_wh_field_num'] = []
    session['first_access_wfield'] = True
    date = request.args.get('editDate')
    department = request.args.get('editDepartment')
    return redirect(url_for('records.edit', editDate=date, editDepartment=department))

@bp.route('/delete', methods=('GET', 'POST'))
@login_required
def delete():
    db = get_db()

    if(g.user['role'] != "GroupLead"):
        dnames = db.execute('''SELECT department_name
                                FROM department_names;''').fetchall()
    else:
        dnames = db.execute('''SELECT department FROM group_lead_department
                                WHERE id = ?;''', (g.user['id'],)).fetchall()


    if request.method == 'POST':
        date = request.form['deleteDate']
        department = request.form['deleteDepartment']

        error = None

        checkExists = db.execute('''SELECT id FROM manufacturinglog
                    WHERE logdate = ? AND department = ?;''', (date, department)).fetchone()

        if checkExists is None:
            error = 'Record does not exist.'

        if not date:
            error = 'Date is required.'

        if not department:
            error = 'Department is required.'

        if error is not None:
            flash(error)
        else:
            idUnit = db.execute('''SELECT id, unitcount
                            FROM manufacturinglog
                            WHERE logdate = ? AND department = ?;''',
                            (date, department)).fetchone()
            nworkers = db.execute('''SELECT manpowercount, manpowerrate
                                    FROM manpowerlog
                                    WHERE ddid = ?
                                    ORDER BY logorder''',
                                    (idUnit[0],)).fetchall()
            workersString = ""
            for n in nworkers:
                (mpc, mpr) = n
                workersString += "<tr><td>{}</td><td>{}</td></tr>".format(mpc, mpr)

            infoDisplayString = '''<div>
                                    <p>Units: {}</p>
                                    <table>
                                        <tr><th>Number of Workers:</th><th>Hours</th></tr>
                                        {}
                                    </table>
                                </div>'''.format(str(idUnit[1]), workersString)
            return redirect(url_for('records.delete_information', dateval=date, depval=department,
            infoDisplayHTML=infoDisplayString, dnames=dnames))

    return render_template('records/delete.html', dnames=dnames)

@bp.route('delete_info', methods=('GET', 'POST'))
@login_required
def delete_information():
    db = get_db()
    if(g.user['role'] != "GroupLead"):
        dnames = db.execute('''SELECT department_name
                                FROM department_names;''').fetchall()
    else:
        dnames = db.execute('''SELECT department FROM group_lead_department
                                WHERE id = ?;''', (g.user['id'],)).fetchall()

    infoDisplayHTML = Markup(request.args.get('infoDisplayHTML'))
    date = request.args.get('dateval')
    department = request.args.get('depval')
    if request.method == 'POST':
        return redirect(url_for('records.delete_confirmation', deleteDate=date, deleteDepartment=department, infoDisplayHTML=infoDisplayHTML, dnames=dnames))
    return render_template('records/delete_info.html', dateval=date, depval=department,
    infoDisplayHTML=infoDisplayHTML, dnames=dnames)


@bp.route('/delete_confirmation', methods=('GET', 'POST'))
@login_required
def delete_confirmation():
    db = get_db()
    if(g.user['role'] != "GroupLead"):
        dnames = db.execute('''SELECT department_name
                                FROM department_names;''').fetchall()
    else:
        dnames = db.execute('''SELECT department FROM group_lead_department
                                WHERE id = ?;''', (g.user['id'],)).fetchall()

    date = request.args.get('deleteDate')
    department = request.args.get('deleteDepartment')
    infoDisplayString = request.args.get('infoDisplayHTML')
    infoDisplayHTML = Markup(infoDisplayString)

    if request.method == 'POST':
        return redirect(url_for('records.delete_success', dateval=date, depval=department))

    return render_template('records/delete_confirmation.html', dateval=date, depval=department,
    infoDisplayHTML=infoDisplayHTML, dnames=dnames)


@bp.route('/delete_success', methods=('GET', 'POST'))
@login_required
def delete_success():
    db = get_db()
    date = request.args.get('dateval')
    department = request.args.get('depval')
    db.execute('''DELETE FROM manpowerlog
                    WHERE ddid = (SELECT id FROM manufacturinglog
                    WHERE logdate = ? AND  department = ?);''',
                    (date, department))
    db.execute('''DELETE FROM manufacturinglog
                    WHERE logdate = ? AND department = ?;''',
                    (date, department))
    db.commit()
    return render_template('records/delete_success.html', date=date, department=department)
