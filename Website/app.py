import flask
from flask import Flask, render_template, request, url_for, redirect, jsonify, flash, session, make_response
from flask_session import Session
from flask_bootstrap import Bootstrap5
from pymongo import MongoClient
import pymongo
import requests
from datetime import datetime 
from pytz import timezone
import pytz
import markdown
import sys
import os.path
import pathlib
import shutil
import json
from bson.objectid import ObjectId
import re
import secrets
import random 
from werkzeug.utils import secure_filename

import constants

app = flask.Flask(__name__)
app.config['UPLOAD_FOLDER'] = sys.path[0] + '/static/images/'            
pathlib.Path(app.config['UPLOAD_FOLDER']).mkdir(exist_ok=True) #creates images folder if it does not exist
app.config['PROFILE_FOLDER'] = sys.path[0] + '/static/images/profiles/'
pathlib.Path(app.config['PROFILE_FOLDER']).mkdir(exist_ok=True) #creates username folder if it does not exist
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = "filesystem"

bootsrtap = Bootstrap5(app)
Session(app)

mongoclient = MongoClient("mongodb://192.168.92.21:27017")
pagecollections = mongoclient["pagecollections"]
wikiarticles = pagecollections["wikiarticles"]
usercollections = mongoclient["usercollections"]
users = usercollections["users"]
commentcollections = mongoclient['commentcollections']
allcomments = commentcollections['comments']
auditcollections = mongoclient['auditcollections']
imageaudit = auditcollections['imageaudit']

tags = ["burn-on-read","user-edit","contains-redacted","all-articles"]
headline = "all profile pictures will need admin approval"
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
CLEANR = re.compile('<redact-el>.*?</redact-el>')
links = [("/","Home Page",""),("/random","Random Article",""),
         ("/articles","Article List",""),("/add","Add an Article",""),
         ("/imageupload","Upload an Image",""),("/login","Login",""),
         ("/register","Register",""),("/logout","Logout",""),("/profile/edit","Edit Profile",""),
         ("/audit/images", "Audit images", "")]

def burn_post(id):
    post_info = wikiarticles.find_one({"_id":id})
    if not post_info:
        return False
    title = post_info.get("title")
    md = post_info.get("md")
    tags = post_info.get("tags")
    created = post_info.get("created")
    edit = post_info.get("edit")
    publish = post_info.get("publish")
    wikiarticles.update_one({"_id":id},{"$set":{"burned":True}})
    return True

def remove_redactel(pagebody):
    cleantext = re.sub(CLEANR,'&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608' + \
        "&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608", pagebody)
    return cleantext


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_loggedin():
    if not 'username' in session:
        session['username'] = None;
    loggedout = not session['username']
    return not loggedout

def is_admin_loggedin():
    username = session['username']
    userdetails = users.find_one({'username': username})
    if userdetails == None:
        return False
    return userdetails.get("is_admin")

def get_routes_loggedin():
    return links

def is_nightmode():
    if not request.cookies.get('nightmode'):
        
        return False
    return request.cookies.get('nightmode')

@app.context_processor
def inject_template_scope():
    injections = dict()

    def cookies_check():
        value = request.cookies.get('cookie_consent')
        return value == 'true' # no boolean zen
    def get_routes():
        return get_routes_loggedin()
    def nightmode_check():
        value = request.cookies.get('nightmode')
        return value == 'true'
    injections.update(cookies_check=cookies_check,nightmode_check=nightmode_check,get_routes=get_routes,headline=headline, timezone=timezone, markdown=markdown)
    
    return injections

@app.route('/',methods=['GET','POST'])
def home_page():
    
    return render_template('homepage.html')

@app.route('/add', methods=['GET', 'POST'])
def add_page():
    if not is_loggedin():
        return redirect(url_for('home_page'))
    if request.method == 'POST':
        article_id = request.form.get("id")
        article_title = request.form.get("title")
        article_body = request.form.get("articleText")
        article_publishdatetime = datetime.strptime(request.form.get("publishDateTime"),'%Y-%m-%dT%H:%M')
        tags_used = request.form.getlist("tagsUsed")
        wikiarticles.insert_one({"_id": article_id, "title":article_title,"md":article_body,"tags":tags_used,"created":datetime.utcnow(),"edit":datetime.utcnow(),"publish":article_publishdatetime,"edited_by": [session['username']], "burned":False})
        return redirect('/content/' + article_id)
    return render_template('add.html', id_readonly="",tags=tags,id="",title="",mdtext="Enter article info here", selected_tags=["user-edit","all-articles"])

@app.route('/imageupload', methods=['GET','POST'])
def image_upload_page():
    if not session['username']:
        return redirect(url_for('home_page'))
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepathq = app.config['UPLOAD_FOLDER'] + 'quarantine/'
            pathlib.Path(app.config['UPLOAD_FOLDER']).mkdir(exist_ok=True)
            pathlib.Path(filepathq).mkdir(exist_ok=True)
            filepath = os.path.join(filepathq, filename)
            if not imageaudit.find_one({'path':filepath}):
                imageaudit.insert_one({'filename':filename,'uploaded_by':session['username'],'path':filepath,'comment':"",'dateuploaded':datetime.utcnow(),'datereleased':None,'quarantined':True, 'audited':False})
            else:
                imageaudit.update_one({'path':filepath}, {"$set":{'uploaded_by':session['username'],'comment':"reuploaded. ",'dateuploaded':datetime.utcnow(),'datereleased':None,'audited':False}})
            file.save(filepath)
            return redirect(url_for('home_page'))#url_for('static', filename=('images/' + filename)))
    return render_template('imageupload.html')

@app.route('/audit/images', methods=['GET','POST'])
def audit_images():
    if not is_admin_loggedin():
        return redirect(url_for('home_page'))
    unauditedimages = imageaudit.find({'audited':False})
    return render_template('audit/imagelist.html', imagelist=unauditedimages)

@app.route('/audit/released/images', methods=['GET','POST'])
def audit_released_images():
    if not is_admin_loggedin():
        return redirect(url_for('home_page'))
    auditedimages = imageaudit.find({'audited': True })
    return render_template('audit/imagelist.html', imagelist=auditedimages)

@app.route('/audit/images/<id>', methods=['GET','POST'])
def audit_image(id):
    if not is_admin_loggedin():
        return redirect(url_for('home_page'))
    unauditedimage = imageaudit.find_one({'_id': ObjectId(id)})
    if not unauditedimage:
        return redirect(url_for('home_page'))
    comment = unauditedimage.get('comment')
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'release' and unauditedimage.get("quarantined"):
            filepath = unauditedimage.get('path')
            newfilepath = filepath.replace('quarantine/', "")
            if not imageaudit.find_one({'path':newfilepath}): # not replacing a new image
                imageaudit.update_one({'_id':ObjectId(id)},{"$set":
                                                            {'path': newfilepath,
                                                            'comment': comment + "  released by " + session['username'] + ".",
                                                            'datereleased': datetime.utcnow(),
                                                            'audited': True,
                                                            'quarantined': False}})
            else: # is replacing released image
                imageaudit.update_one({'path': newfilepath}, {"$set":
                                                              {'comment': comment + " released by " + session['username'] + ". File overwritten.",
                                                               'audited': True,
                                                               'quarantined':False,
                                                               'datereleased': datetime.utcnow()}})
                imageaudit.delete_one({'_id': ObjectId(id)})
            shutil.move(filepath, newfilepath)
        elif action == 'delete':
            imageaudit.delete_one({'_id':ObjectId(id)})
            if os.path.isfile(unauditedimage.get('path')):
                os.remove(unauditedimage.get('path'))
        elif action == 'quarantine' and not unauditedimage.get("quarantined"):
            pass
        else:
            pass
        return redirect(url_for('audit_images'))
    return render_template('audit/imageaudit.html',unauditedimage=unauditedimage)


@app.route('/content/<id>', methods=['GET','POST'])
def content_page(id):
    return render_template('content.html',id=id)

@app.route('/page/<id>', methods=['GET','POST'])
def site_page(id):
    
    page_info = wikiarticles.find_one({"_id": id})
    if not page_info or page_info.get("burned"):
        return redirect(url_for('page_not_found'))
    title = page_info.get("title")
    mdtext = page_info.get("md")
    pagebody = remove_redactel(markdown.markdown(mdtext))
    lastedit = page_info.get("edit")
    publish = page_info.get("publish")
    if publish > datetime.utcnow() and not is_admin_loggedin():
        return redirect(url_for('home_page'))
    edited_by = page_info.get('edited_by')
    comments = allcomments.find({'post_id':id}).sort('date',pymongo.ASCENDING) # ASCENDING for oldest comments first
    tags_used = page_info.get("tags")
    if "burn-on-read" in tags_used:
        burn_post(id)
    if request.method == 'POST' and session['username']:
        comment = request.form.get('comment')
        allcomments.insert_one({'post_id':id,'username': session['username'], 'comment':comment,'date':datetime.utcnow(), 'audited': False})
        return redirect('/page/' + id)
    return render_template('page.html',id=id,loggedin=is_loggedin(), title=title, pagebody=pagebody, page_id=id, tags=tags_used, lastedit=lastedit, edited_by=edited_by, comments=comments, users=users)

@app.route('/page/edit/<id>', methods=['GET','POST'])
def edit_site_page(id):
    if not is_loggedin():
        return redirect('/page/' + id)
    page_info = wikiarticles.find_one({"_id": id})
    if not page_info or page_info.get("burned"):
        return redirect(url_for('page_not_found'))
    title = page_info.get("title")
    mdtext = page_info.get("md")
    datecreated = page_info.get("created")
    selected_tags = page_info.get("tags")
    edited_by = page_info.get("edited_by")
    #pagebody= markdown.markdown(mdtext)
    # to-do add tags
    if request.method == 'POST':
        article_title = request.form.get("title")
        article_body = request.form.get("articleText")
        article_publishdatetime = datetime.strptime(request.form.get("publishDateTime"), '%Y-%m-%dT%H:%M')
        tags_used = request.form.getlist("tagsUsed")
        if session['username'] not in edited_by:
            edited_by.append(session['username'])
        wikiarticles.delete_one({"_id":id})
        wikiarticles.insert_one({"_id": id, "title":article_title,"md":article_body,"tags":tags_used,"created":datecreated,"edit":datetime.utcnow(),"publish":article_publishdatetime, "edited_by": edited_by ,"burned":False})
        return redirect('/content/' + id)
    return render_template('add.html',id_readonly="readonly",tags=tags,id=id,title=title,mdtext=mdtext, selected_tags=selected_tags)

@app.route('/page/edit/upload/<id>', methods=['GET','POST'])
def post_upload(id):
    if not session['username']:
        return redirect('/page/' + id)
    
    if request.method == 'POST':
        files = request.files.getlist('file')
        for file in files:
            page_info = wikiarticles.find_one({'_id': id})
            if not page_info:
                return redirect('/page/' + id)
            edited_by = page_info.get('edited_by')
            if not session['username'] in edited_by:
                edited_by.append(session['username'])
            if 'file' not in request.files:
                return ('No file part')
                return redirect(request.url)
        # If the user does not select a file, the browser submits an
        # empty file without a filename
            if file.filename == '':
                return ('No selected file')
                return redirect(request.url)
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepathq = app.config['UPLOAD_FOLDER'] + 'quarantine/'
                pathlib.Path(app.config['UPLOAD_FOLDER']).mkdir(exist_ok=True)
                pathlib.Path(filepathq).mkdir(exist_ok=True)
                filepath = os.path.join(filepathq, filename)
                if not imageaudit.find_one({'path':filepath}):
                    imageaudit.insert_one({'filename':filename,'uploaded_by':session['username'],'path':filepath,'comment':"",'dateuploaded':datetime.utcnow(),'datereleased':None,'quarantined':True, 'audited':False})
                else:
                    imageaudit.update_one({'path':filepath}, {"$set":{'uploaded_by':session['username'],'comment':"reuploaded. ",'dateuploaded':datetime.utcnow(),'datereleased':None,'audited':False}})
                wikiarticles.update_one({'_id':id}, {'$set':{'md':page_info.get('md')+'![link](/static/images/' + filename + ')  ', 'edited_by':edited_by,'edit':datetime.utcnow()}})
                file.save(filepath)
        return redirect('/page/'+id )#url_for('static', filename=('images/' + filename))
    return render_template('audit/imagepostupload.html', id=id)

@app.route('/profile/<username>', methods=['GET','POST'])
def profile_page(username):
    if not session['username']:
        pass
    is_user_viewing = session['username'] == username
    is_admin_viewing = is_admin_loggedin()
    user_info = users.find_one({'username':username})
    if not user_info:
        return redirect(url_for('home_page'))
    profilepic = user_info.get('profilepic')
    bio = remove_redactel(markdown.markdown(user_info.get('bio')))
    faction = user_info.get('faction')
    admin_status = user_info.get('is_admin')
    date_created = user_info.get('created')
    lastlogin = user_info.get('lastlogin')
    return render_template('session/profile.html', username=username,
                        profilepic=profilepic, bio=bio, faction=faction,
                        admin_status=admin_status, date_created=date_created,
                       lastlogin=lastlogin, is_user_viewing=is_user_viewing, is_admin_viewing_=is_admin_viewing)

@app.route('/profile/edit',methods=['GET','POST'])
def redirect_edit_profile_page():
    if session['username']:
        return redirect('/profile/edit/' + session['username'])
    return redirect(url_for('login_page'))

@app.route('/profile/edit/<username>', methods=['GET','POST'])
def edit_profile_page(username):
    if not session['username'] == username and not is_admin_loggedin():
        return redirect('/profile/' + username)
    user_info = users.find_one({'username':username})
    if not user_info:
        return redirect(url_for('register_page'))
    profilepic = user_info.get("profilepic")
    bio = user_info.get("bio")
    faction = user_info.get("faction")
    admin_status = user_info.get("is_admin")
    date_created = user_info.get("created")
    lastlogin = user_info.get("lastlogin")
    lastprofilechange = datetime.utcnow() 
    if request.method == 'POST':
        bio = request.form.get("bio")
        if 'file' not in request.files:
            flash('No file part')
        else:
            file = request.files['file']
            # If the user does not select a file, the browser submits an
            # empty file without a filename
            if file.filename == '':
                flash('No selected file')
            else:
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    profilepic = filename
                    pathlib.Path(app.config['PROFILE_FOLDER'],username).mkdir(exist_ok=True) #creates username folder if it does not exist
                    pathlib.Path(app.config['PROFILE_FOLDER'],username + '/quarantine/').mkdir(exist_ok=True) #creates username folder if it does not exist
                    filepath = os.path.join(app.config['PROFILE_FOLDER'] + username + '/quarantine/', filename)
                    if not imageaudit.find_one({'path':filepath}):
                        imageaudit.insert_one({'filename':filename,'uploaded_by':session['username'],'path':filepath,'comment': "",'dateuploaded':datetime.utcnow(),'datereleased':None,'quarantined':True, 'audited':False})
                    else:
                        imageaudit.update_one({'path':filepath}, {"$set":{'uploaded_by':session['username'],'comment': "reuploaded. ", 'dateuploaded':datetime.utcnow(),'datereleased':None,'audited':False}})
                    file.save(filepath)

        users.update_one({'username':username},  {"$set": {"lastprofilechange":datetime.utcnow(), "bio":bio, "profilepic":profilepic}})
        return redirect('/profile/' + username)
    return render_template('session/editprofile.html', username=username, profilepic=profilepic, bio=bio, faction=faction,  admin_status=admin_status, date_created=date_created, lastlogin=lastlogin)


@app.route('/articles', methods=['GET', 'POST'])
def articles_page():
    allarticles = list(wikiarticles.find())
    for i in allarticles:
        if i.get("burned"):
            allarticles.remove(i)
    numarticles = len(allarticles)
    if numarticles <= 0:
        return "no pages are set up"
    return render_template('pagelist.html',articles=allarticles)

@app.route('/random', methods=['GET', 'POST'])
def random_page():
    allarticles = list(wikiarticles.find())
    for i in allarticles:
        if i.get("burned"):
            allarticles.remove(i)
    numarticles = len(allarticles)
    articleselected = random.randrange(numarticles)
    if numarticles <= 0:
        return "no pages are set up"
    return redirect('/page/' + allarticles[articleselected].get("_id"))

@app.route('/nightmode', methods=['GET','POST']) # for toggling night mode
def nightmode_page():
    resp = make_response('Setting the cookie') 
    resp.set_cookie('GFG','ComputerScience Portal')
    stang = ""
    for x in request.cookies:
        stang += x + ": "+ request.cookies.get(x) + "      "
    return stang
    return redirect('/')

#to-do
@app.route('/pagenotfound')
def page_not_found():
    return "lol"

#to-do
@app.route('/users', methods=['GET','POST'])
def users_page():
    return "list users here"

@app.route('/login', methods=['GET','POST'])
def login_page():
    if request.method == 'POST':
        # record the username
        username = request.form.get("inputUsername")
        userdetails = users.find_one({"username":username})
        hash_pass = request.form.get("inputPassword")
        if not userdetails or not userdetails.get("password") == hash_pass:
            return redirect(url_for("login_page"))
        else :
            session["username"] = username
            users.update_one({"username":username},
                {"$set": {"lastlogin":datetime.utcnow()}})
        return redirect(url_for('home_page'))

    return render_template('session/login.html')

@app.route('/register', methods=['GET','POST'])
def register_page():
    if request.method == 'POST':
        username = request.form.get("inputUsername")
        if users.find_one({'username':username}):
            return redirect(url_for('register_page'))
        email = request.form.get("inputEmail")
        password = request.form.get("inputPassword")
        adminpassword = request.form.get("inputAdminPassword")
        is_admin = adminpassword == "butts"
        users.insert_one({"username":username,"email":email,"password":password,"faction": "","profilepic":"", "bio": "", "is_admin": is_admin,"created":datetime.utcnow(),"lastlogin":datetime.utcnow(),"lastprofilechange":datetime.utcnow()})
        return redirect(url_for('login_page'))
    return render_template('session/register.html')

@app.route('/logout', methods=['GET','POST'])
def logout():
    #session.pop('username')
    session['username'] = None
    return redirect(url_for('home_page'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port = 80)