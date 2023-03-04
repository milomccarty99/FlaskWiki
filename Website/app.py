import flask
from flask import Flask, render_template, request, url_for, redirect, jsonify, flash, session
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
bootsrtap = Bootstrap5(app)

mongoclient = MongoClient("mongodb://192.168.92.21:27017")
pagecollections = mongoclient["pagecollections"]
wikiarticles = pagecollections["wikiarticles"]
usercollections = mongoclient["usercollections"]
users = usercollections["users"]

tags = ["burn-on-read","user-edit","contains-redacted","all-articles"]

@app.route('/',methods=['GET','POST'])
def home_page():
    return render_template('homepage.html')

@app.route('/add', methods=['GET', 'POST'])
def add_page():
    if request.method == 'POST':
        article_id = request.form.get("id")
        article_title = request.form.get("title")
        article_body = request.form.get("articleText")
        article_publishdatetime =  datetime.strptime(request.form.get("publishDateTime"),'%Y-%m-%dT%H:%M')
        # to-do add tags
        wikiarticles.insert_one({"_id": article_id, "title":article_title,"md":article_body,"created":datetime.utcnow(),"edit":datetime.utcnow(),"publish":article_publishdatetime})
        return redirect('/page/' + article_id)
    return render_template('add.html', id_readonly="",tags=tags,id="",title="",mdtext="Enter article info here", selected_tags=["user-edit"])

@app.route('/page/<id>', methods=['GET','POST'])
def site_page(id):
    page_info = wikiarticles.find_one({"_id": id})
    if not page_info:
        return redirect(url_for('page_not_found'))
    title = page_info.get("title")
    mdtext = page_info.get("md")
    pagebody= markdown.markdown(mdtext)
    # to-do add tags
    return render_template('page.html',id=id,title=title,pagebody=pagebody, page_id=id)

@app.route('/page/edit/<id>', methods=['GET','POST'])
def edit_site_page(id):
    page_info = wikiarticles.find_one({"_id": id})
    if not page_info:
        return redirect(url_for('page_not_found'))
    title = page_info.get("title")
    mdtext = page_info.get("md")
    #pagebody= markdown.markdown(mdtext)
    # to-do add tags
    return render_template('add.html',id_readonly="readonly",tags=tags,id=id,title=title,mdtext=mdtext, selected_tags=["user-edit"])
    
    
    
    if request.method == 'POST':

        article_id = request.form.get("id")
        if not (article_id == id):
            return redirect(url_for('edit_site_page',id=id))
        article_title = request.form.get("title")
        article_body = request.form.get("articleText")
        article_publishdatetime = datetime.strptime(request.form.get("publishDateTime"), '%Y-%m-%dT%H:%M')
        wikiarticles.delete_one({"_id":article_id})
        wikiarticles.insert_one({"_id": article_id, "title":article_title,"md":article_body,"created":datetime.utcnow(),"edit":datetime.utcnow(),"publish":article_publishdatetime})

    return "editing " + str(id)

@app.route('/articles', methods=['GET', 'POST'])
def articles_page():
    allarticles = list(wikiarticles.find())
    numarticles = len(allarticles)
    if numarticles <= 0:
        return "no pages are set up"
    return render_template('pagelist.html',articles=allarticles)

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
        pass
    return render_template('session/login.html')

@app.route('/register', methods=['GET','POST'])
def register_page():
    if request.method == 'POST':
        pass
    return render_template('session/register.html')

@app.route('/logout', methods=['GET','POST'])
def logout():
    #session.pop('username')
    return redirect(url_for('home_page'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port = 80)