import flask
from flask import Flask, render_template, request, url_for, redirect, jsonify, flash, session
from flask_session import Session
from flask_bootstrap import Bootstrap5
from pymongo import MongoClient
import requests
from datetime import datetime 
import markdown
import sys
import os.path
import pathlib
import json
import re
import secrets
import random 
from werkzeug.utils import secure_filename

import constants

app = flask.Flask(__name__)
app.config['UPLOAD_FOLDER'] = sys.path[0] + '/static/images/'
app.config['PROFILE_FOLDER'] = sys.path[0] + '/static/images/profiles/'
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

tags = ["burn-on-read","user-edit","contains-redacted","all-articles"]
headline = "Introduce it in Act I"
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
CLEANR = re.compile('<redact-el>.*?</redact-el>')
links = [("/","Home Page",""),("/random","Random Article",""),
         ("/articles","Article List",""),("/add","Add an Article",""),
         ("/imageupload","Upload an Image",""),("/login","Login",""),
         ("/register","Register",""),("/logout","Logout",""),("/profile/edit","Edit Profile","")]

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
    wikiarticles.delete_one({"_id":id})
    wikiarticles.insert_one({"_id":id,"title":title,"md":md,"tags":tags,"created":created,"edit":edit,"publish":publish,"burned":True})
    return True

def remove_redactel(pagebody):
    cleantext = re.sub(CLEANR,'&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608' + \
        "&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608&#9608", pagebody)
    return cleantext


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_loggedin():
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

@app.context_processor
def inject_template_scope():
    injections = dict()

    def cookies_check():
        value = request.cookies.get('cookie_consent')
        return value == 'true' # no boolean zen
    def get_routes():
        return get_routes_loggedin()
    injections.update(cookies_check=cookies_check,get_routes=get_routes,headline=headline)
    
    return injections

@app.route('/',methods=['GET','POST'])
def home_page():
    if not session.get("username"):
        return redirect("/login")
    return render_template('homepage.html', headline=headline)

@app.route('/add', methods=['GET', 'POST'])
def add_page():
    if not is_loggedin():
        return redirect(url_for('home_page'))
    if request.method == 'POST':
        article_id = request.form.get("id")
        article_title = request.form.get("title")
        article_body = request.form.get("articleText")
        article_publishdatetime =  datetime.strptime(request.form.get("publishDateTime"),'%Y-%m-%dT%H:%M')
        tags_used = request.form.getlist("tagsUsed")
        wikiarticles.insert_one({"_id": article_id, "title":article_title,"md":article_body,"tags":tags_used,"created":datetime.utcnow(),"edit":datetime.utcnow(),"publish":article_publishdatetime,"edited_by": [session['username']], "burned":False})
        return redirect('/content/' + article_id)
    return render_template('add.html', id_readonly="",tags=tags,id="",title="",mdtext="Enter article info here", selected_tags=["user-edit","all-articles"])

@app.route('/imageupload', methods=['GET','POST'])
def image_upload_page():
    if not is_admin_loggedin():
        return redirect(url_for('home_page'))
    if request.method == 'POST':
        if 'file' not in  request.files:
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
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            return redirect(url_for('home_page'))#url_for('static', filename=('images/' + filename)))
    return render_template('imageupload.html')

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
    pagebody= remove_redactel(markdown.markdown(mdtext))
    
    tags_used = page_info.get("tags")
    if "burn-on-read" in tags_used:
        burn_post(id)
    return render_template('page.html',id=id,title=title,pagebody=pagebody, page_id=id, tags=tags_used)

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
        if not session['username'] or session['username'] not in edited_by:
            edited_by.append(session['username'])
        wikiarticles.delete_one({"_id":id})
        wikiarticles.insert_one({"_id": id, "title":article_title,"md":article_body,"tags":tags_used,"created":datecreated,"edit":datetime.utcnow(),"publish":article_publishdatetime, "edited_by": edited_by ,"burned":False})
        return redirect ('/content/' + id)
    return render_template('add.html',id_readonly="readonly",tags=tags,id=id,title=title,mdtext=mdtext, selected_tags=selected_tags)

@app.route('/profile/<username>', methods=['GET','POST'])
def profile_page(username):
    if not session['username']:
        return redirect(url_for('home_page'))
    is_user_viewing = session['username'] == username
    is_admin_viewing = is_admin_loggedin()
    user_info = users.find_one({'username':username})
    if not user_info:
        return redirect(url_for('home_page'))
    profilepic = user_info.get('profilepic')
    bio = remove_redactel( markdown.markdown( user_info.get('bio')))
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
        if 'file' not in  request.files:
            flash('No file part')
            return "no file part"
        else:
            file = request.files['file']
            # If the user does not select a file, the browser submits an
            # empty file without a filename
            if file.filename == '':
                flash('No selected file')
                return "no selected file"
            else:
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    profilepic = filename
                    pathlib.Path(app.config['PROFILE_FOLDER'],username).mkdir(exist_ok=True) #creates username folder if it does not exist
                    file.save(os.path.join(app.config['PROFILE_FOLDER'] + username + '/', filename))


        users.update_one({'username':username},  {"$set": {"lastprofilechange":datetime.utcnow(), "bio":bio, "profilepic":profilepic}})
        return redirect('/profile/'+username)
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

@app.route('/pagenotfound')
def page_not_found():
    return "lol"

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
            users.update_one(
                {"username":username},
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