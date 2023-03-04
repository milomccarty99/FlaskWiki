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
import json
import re
import secrets
import random 
from werkzeug.utils import secure_filename

import constants

app = flask.Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/images'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = "filesystem"

bootsrtap = Bootstrap5(app)
Session(app)

mongoclient = MongoClient("mongodb://192.168.92.21:27017")
pagecollections = mongoclient["pagecollections"]
wikiarticles = pagecollections["wikiarticles"]
usercollections = mongoclient["usercollections"]
users = usercollections["users"]

tags = ["burn-on-read","user-edit","contains-redacted","all-articles"]
headline = "Ian, check your messages"


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

@app.context_processor
def inject_template_scope():
    injections = dict()

    def cookies_check():
        value = request.cookies.get('cookie_consent')
        return value == 'true' # no boolean zen
    injections.update(cookies_check=cookies_check)
    
    return injections

@app.route('/',methods=['GET','POST'])
def home_page():
    if not session.get("username"):
        return redirect("/login")
    return render_template('homepage.html', headline=headline)

@app.route('/add', methods=['GET', 'POST'])
def add_page():
    if request.method == 'POST':
        article_id = request.form.get("id")
        article_title = request.form.get("title")
        article_body = request.form.get("articleText")
        article_publishdatetime =  datetime.strptime(request.form.get("publishDateTime"),'%Y-%m-%dT%H:%M')
        tags_used = request.form.getlist("tagsUsed")
        wikiarticles.insert_one({"_id": article_id, "title":article_title,"md":article_body,"tags":tags_used,"created":datetime.utcnow(),"edit":datetime.utcnow(),"publish":article_publishdatetime, "burned":False})
        return redirect('/content/' + article_id)
    return render_template('add.html', id_readonly="",tags=tags,id="",title="",mdtext="Enter article info here", selected_tags=["user-edit","all-articles"], headline=headline)

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
    pagebody= markdown.markdown(mdtext)
    tags_used = page_info.get("tags")
    if "burn-on-read" in tags_used:
        burn_post(id)
    return render_template('page.html',id=id,title=title,pagebody=pagebody, page_id=id, tags=tags_used, headline=headline)

@app.route('/page/edit/<id>', methods=['GET','POST'])
def edit_site_page(id):
    page_info = wikiarticles.find_one({"_id": id})
    if not page_info or page_info.get("burned"):
        return redirect(url_for('page_not_found'))
    title = page_info.get("title")
    mdtext = page_info.get("md")
    datecreated = page_info.get("created")
    selected_tags = page_info.get("tags")
    #pagebody= markdown.markdown(mdtext)
    # to-do add tags
    if request.method == 'POST':
        article_title = request.form.get("title")
        article_body = request.form.get("articleText")
        article_publishdatetime = datetime.strptime(request.form.get("publishDateTime"), '%Y-%m-%dT%H:%M')
        tags_used = request.form.getlist("tagsUsed")
        wikiarticles.delete_one({"_id":id})
        wikiarticles.insert_one({"_id": id, "title":article_title,"md":article_body,"tags":tags_used,"created":datecreated,"edit":datetime.utcnow(),"publish":article_publishdatetime, "burned":False})
        return redirect ('/content/' + id)
    return render_template('add.html',id_readonly="readonly",tags=tags,id=id,title=title,mdtext=mdtext, selected_tags=selected_tags, headline=headline)

@app.route('/articles', methods=['GET', 'POST'])
def articles_page():
    allarticles = list(wikiarticles.find())
    numarticles = len(allarticles)
    if numarticles <= 0:
        return "no pages are set up"
    return render_template('pagelist.html',articles=allarticles, headline=headline)

@app.route('/random', methods=['GET', 'POST'])
def random_page():
    allarticles = list(wikiarticles.find())
    numarticles = len(allarticles)
    if numarticles <= 0:
        return "no pages are set up"
    articleselected = random.randrange(numarticles)
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
        session["username"] = request.form.get("inputUsername")
        return redirect(url_for('home_page'))

    return render_template('session/login.html', headline=headline)

@app.route('/register', methods=['GET','POST'])
def register_page():
    if request.method == 'POST':
        pass
    return render_template('session/register.html', headline=headline)

@app.route('/logout', methods=['GET','POST'])
def logout():
    #session.pop('username')
    session['username'] = None
    return redirect(url_for('home_page'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port = 80)