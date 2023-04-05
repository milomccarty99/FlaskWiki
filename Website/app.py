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
import joblib
import sklearn.externals
from profanity_check import predict, predict_prob

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
consolecollections = mongoclient["consolecollections"]
admindata = consolecollections['admindata']
tagdata = consolecollections['tagdata']
linksdata = consolecollections['linksdata']
prioritizesearch = consolecollections['prioritizesearch']
ipdata = consolecollections['ipdata']
pagecollections = mongoclient["pagecollections"]
wikiarticles = pagecollections["wikiarticles"]
usercollections = mongoclient["usercollections"]
users = usercollections["users"]
commentcollections = mongoclient['commentcollections']
allcomments = commentcollections['comments']
auditcollections = mongoclient['auditcollections']
imageaudit = auditcollections['imageaudit']


ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
CLEANR = re.compile('<redact-el>.*?</redact-el>')

def site_setup():
    if is_admin_loggedin():
        return
    else:
        admindata.insert_one({'_id':'headline','headline':'welcome to the site wiki'})
        admindata.insert_one({'_id':'adminpassword','password':'butts'})
        admindata.insert_one({'_id':'featuredarticle','featuredarticle':'first_article'})
        admindata.insert_one({'_id':'mcserverip','mcserverip':'type ip address here'})
        tagdata.insert_one({'tag':'burn-on-read', 'priority': 1,'datecreated':datetime.utcnow(),'selected':False, 'comment':""})
        tagdata.insert_one({'tag':'user-edit', 'priority':1,'datecreated':datetime.utcnow(), 'selected':True, 'comment':""})
        tagdata.insert_one({'tag':'all-articles','priority':1, 'datecreated':datetime.utcnow(),'selected':True,'comment':""})
        wikiarticles.insert_one({'_id':'first_article','title':'Founding Article','md':'','tags':[],'created':datetime.utcnow(),'edit':datetime.utcnow(),'publish':datetime.utcnow(),'burned':False})
        wikiarticles.insert_one({'_id':'leaderboard','title':'Leaderboard','md':'','tags':['all-articles'],'created':datetime.utcnow(),'edit':datetime.utcnow(),'publish':datetime.utcnow(),'burned':False})
        linksdata.insert_one({'route':'/','name':'Home Page','priority':1,'is_section_head':False,'tag':'all'})
        linksdata.insert_one({'route':'/random','name': 'Random Article', 'priority':2,'is_section_head':False,'tag':'all'})
        linksdata.insert_one({'route':'/tag/all-articles', 'name':'All Articles','priority':3,'is_section_head':True,'tag':'all'})
        linksdata.insert_one({'route':'/tagslist', 'name':'Categories','priority':4,'is_section_head':True, 'tag':'all'})
        linksdata.insert_one({'route':'/add', 'name': 'Add an Article', 'priority':3,'is_section_head': False, 'tag':'user'})
        linksdata.insert_one({'route':'/imageupload','name':'Upload an Image', 'priority':4,'is_section_head':False, 'tag':'user'})
        linksdata.insert_one({'route':'/page/report_bugs','name':'Report a Bug','priority':5,'is_section_head':False,'tag':'user'})
        linksdata.insert_one({'route':'/login','name':'Login','priority':5,'is_section_head':False,'tag':'logged-out'})
        linksdata.insert_one({'route':'/register', 'name':'Register','priority':6,'is_section_head':False,'tag':'logged-out'})
        linksdata.insert_one({'route':'/logout', 'name': 'Logout','priority':5,'is_section_head':False,'tag':'user'})
        linksdata.insert_one({'route':'/adminconsole','name': 'Admin Console', 'priority':6,'is_section_head': True, 'tag':'admin-console'})
        linksdata.insert_one({'route': '/audit/images','name':'Audit Images','priority':6,'is_section_head':False,'tag':'admin'})
        linksdata.insert_one({'route':'/audit/released/images','name':'Manage Images','priority':7, 'is_section_head':False,'tag':'admin'})
        linksdata.insert_one({'route':'/routelinks','name' :'Route Links','priority':6,'is_section_head':False,'tag':'admin'})
        linksdata.insert_one({'route':'/tags','name':'Tags','priority':6,'is_section_head':False,'tag':'admin'})
        linksdata.insert_one({'route':'/headline','name':'Headline','priority':6,'is_section_head':False,'tag':'admin'})
        linksdata.insert_one({'route':'/adminpassword','name':'Admin Password','priority':6,'is_section_head':False,'tag':'admin'})
        linksdata.insert_one({'route':'/mcserverip','name':'MC Server IP','priority':6,'is_section_head':False,'tag':'admin'})
        linksdata.insert_one({'route':'/users','name':'Users List','priority':7,'is_section_head':False,'tag':'admin'})
        linksdata.insert_one({'route':'/modserach/proritize', 'name':'Prioritize Article','priority': 6,'is_section_head':False,'tag':'admin'})
        linksdata.insert_one({'route':'/modsearch/seeprioritized','name':'See Prioritized','priority':6,'is_section_head':False,'tag':'admin'})
        linksdata.insert_one({'route':'/audit/comments','name':'Audit Comments','priority':6,'is_section_head':False,'tag':'admin'})
        linksdata.insert_one({'route':'/audit/articles','name':'Audit Articles','priority':6,'is_section_head':False,'tag':'admin'})

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
    if not 'username' in session:
        session['username'] = None
    username = session['username']
    userdetails = users.find_one({'username': username})
    if userdetails == None:
        return False
    return userdetails.get("is_admin")

def get_routes_loggedin():
    results = list(linksdata.find({'tag':'all'}))
    if is_loggedin():
        results.extend(list(linksdata.find({'tag':'user'})))
    else:
        results.extend(list(linksdata.find({'tag':'logged-out'})))
    if is_admin_loggedin():
        results.extend(list(linksdata.find({'tag':'admin-console'})))
    return results

def get_tags():
    alltags = tagdata.find()
    result = []
    for tag in alltags:
        result.append(tag.get('tag'))
    return result

def is_nightmode():
    if not request.cookies.get('nightmode'):
        
        return False
    return request.cookies.get('nightmode')

@app.context_processor
def inject_template_scope():
    injections = dict()
    def get_site_headline():
        headlinedata = admindata.find_one({'_id':'headline'})
        if not headlinedata:
            return "Wiki setup required"
        return headlinedata.get("headline")
    def cookies_check():
        value = request.cookies.get('cookie_consent')
        if not value:
            return False
        return value == 'true' # no boolean zen
    def get_routes():
        return get_routes_loggedin()
    def nightmode_check():
        value = request.cookies.get('nightmode')
        return value == 'true'
    injections.update(cookies_check=cookies_check,nightmode_check=nightmode_check,get_routes=get_routes,headline=get_site_headline(), timezone=timezone, markdown=markdown)
    
    return injections

@app.route('/',methods=['GET','POST'])
def home_page():
    atp = admindata.find_one({'_id':'featuredarticle'}).get('featuredarticle')
    articletopreview = wikiarticles.find_one({'_id':atp})
    articlepagebody = remove_redactel(markdown.markdown(articletopreview.get("md")))
    leaderboardarticle = wikiarticles.find_one({'_id':'current-events'})
    leaderboard = (leaderboardarticle.get("md"))
    mcserverip = admindata.find_one({'_id':'mcserverip'}).get('mcserverip')
    return render_template('homepage.html', articlepagebody=articlepagebody,articletitle=articletopreview.get('title'), articleid = articletopreview.get('_id'),leaderboard=leaderboard, mcserverip=mcserverip)

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
    return render_template('add.html', id_readonly="",tags=get_tags(),id="",title="",mdtext="Enter article info here", selected_tags=["user-edit","all-articles"])

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

@app.route('/audit/comments', methods=['GET','POST'])
def audit_comments_page():
    if not is_admin_loggedin():
        return redirect(url_for('home_page'))
    sortedcomments = allcomments.find({"audited":False}).sort('profanity_score',pymongo.DESCENDING)
    return render_template('audit/commentaudit.html', comments=sortedcomments)

@app.route('/audit/comment/delete/<id>', methods=['GET','POST'])
def audit_comment_delete_page(id):
    if not is_admin_loggedin():
        return redirect(url_for('home_page'))
    allcomments.delete_one({'_id':ObjectId(id)})
    return redirect(url_for('audit_comments_page'))

@app.route('/audit/articles', methods=['GET','POST'])
def audit_articles_page():
    if not is_admin_loggedin():
        return redirect(url_for('home_page'))
    allarticles = list(wikiarticles.find())
    profanityscores = []
    for i in allarticles:
        score = predict_prob([i.get('md')])[0]
        profanityscores.append(score)

    return render_template('audit/articleaudit.html',allarticles=allarticles, profanityscores=profanityscores)

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


@app.route('/adminconsole', methods=['GET','POST'])
def admin_console_page():
    if not is_admin_loggedin():
        return redirect(url_for('home_page'))
    linkroutes = list(linksdata.find({'tag':'admin'}))
    return render_template('management/adminconsole.html', linkroutes=linkroutes)


@app.route('/servermap', methods=['GET','POST'])
def mcserver_map_page():
    mcserverip = admindata.find_one({'_id':'mcserverip'}).get('mcserverip')
    return render_template('mcservermap.html', mcserverip=mcserverip)

@app.route('/content/<id>', methods=['GET','POST'])
def content_page(id):
    return render_template('content.html',id=id)

@app.route('/page/<id>', methods=['GET','POST'])
def site_page(id):
    
    page_info = wikiarticles.find_one({"_id": id})
    if page_info.get("burned") and not is_admin_loggedin():
        return "lul"
    if not page_info:
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
        profanity_score = predict_prob([comment])[0]
        allcomments.insert_one({'post_id':id,'username': session['username'], 'comment':comment,'profanity_score': profanity_score,'date':datetime.utcnow(), 'audited': False})
        return redirect('/page/' + id)
    return render_template('page.html',id=id,loggedin=is_loggedin(), title=title, pagebody=pagebody, page_id=id, tags=tags_used, lastedit=lastedit, edited_by=edited_by, comments=comments, users=users)

@app.route('/page/delete/<id>', methods=['GET','POST'])
def delete_site_page(id):
    if not is_admin_loggedin():
        return redirect(url_for('home_page'))
    wikiarticles.delete_one({'_id':id})
    return redirect(url_for('home_page'))

@app.route('/page/delete', methods=['GET','POST'])
def delete_site_article_page():
    if not is_admin_loggedin():
        return redirect(url_for('home_page'))
    allarticles = list(wikiarticles.find())

    return render_template('management/deletearticles.html',allarticles=allarticles)

@app.route('/page/edit/<id>', methods=['GET','POST'])
def edit_site_page(id):
    if not is_loggedin():
        return redirect('/page/' + id)
    page_info = wikiarticles.find_one({"_id": id})
    if not page_info or page_info.get("burned"):
        return redirect(url_for('page_not_found'))
    if not is_admin_loggedin() and not 'user-edit' in page_info.get('tags'):
        return redirect('/page/' + id)
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
    return render_template('add.html',id_readonly="readonly",tags=get_tags(),id=id,title=title,mdtext=mdtext, selected_tags=selected_tags)

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

@app.route('/page/edit/addlinks/<id>', methods=['GET','POST'])
def page_link_page(id):
    page_info = wikiarticles.find_one({'_id':id})
    if not page_info:
        return redirect(url_for('home_page'))
    if not is_loggedin():
        return redirect('/page/'+id)
    if request.method == 'POST':
        edited_by = page_info.get('edited_by')
        if session['username'] not in edited_by:
            edited_by.append(session['username'])
        for articlelink in request.form:
            # not efficient use of update
            page_info = wikiarticles.find_one({'_id':id})
            wikiarticles.update_one({'_id':id},{"$set":{'md':page_info.get('md')+'['+ articlelink+'](/page/'+articlelink + ')  ', 'edited_by': edited_by,'edit':datetime.utcnow()}})
        return redirect('/page/' + id)
    allarticles = list(wikiarticles.find({'burned':False}))
    return render_template('articlelink.html', articles=allarticles)

@app.route('/tag/<tagname>', methods=['GET','POST'])
def tag_preview_page(tagname):
    allarticles = list(wikiarticles.find({'burned':False}).sort('title',pymongo.ASCENDING))
    result = []
    for i in allarticles:
        if tagname in i.get('tags') and (i.get('publish')<=  datetime.utcnow() or is_admin_loggedin()):
            result.append(i)

    return render_template('taginfo.html', tagname=tagname, articles=result)


@app.route('/profile', methods=['GET'])
def redirect_profile_page():
    if not is_loggedin():
        return redirect(url_for('login_page'))
    return redirect('/profile/' + session['username'])

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


@app.route('/search/<query>', methods=['GET','POST'])
def search_page(query):
    allarticles = list(wikiarticles.find({"burned":False}))
    allpriority = list(prioritizesearch.find())
    for i in allpriority:
        if wikiarticles.find_one({'_id':i.get('_id')}).get('publish') > datetime.utcnow():
            allpriority.remove(i)
    for i in allarticles:
        if i.get("publish") > datetime.utcnow():
            allarticles.remove(i)
    results = []
    for i in allpriority:
        article = wikiarticles.find_one({'_id':i.get('_id')})
        if query.lower() in remove_redactel(article.get("md")).lower():
            results.append(article)
        elif query.lower() in remove_redactel(article.get("title")).lower():
            results.append(article)
    for i in allarticles:
        if query.lower() in remove_redactel(i.get("md")).lower():
            if not i in results:
                results.append(i)
        elif query.lower() in remove_redactel(i.get("title")).lower():
            if not i in results:
                results.append(i)
    return render_template('articlelist.html',articlelist=results)

@app.route('/modsearch/prioritize', methods=['GET','POST'])
def search_proritize_page():
    if not is_admin_loggedin():
        return redirect(url_for('home_page'))
    allarticles = list(wikiarticles.find())
    for i in allarticles:
        if prioritizesearch.find_one({'_id':i.get('_id')}):
            allarticles.remove(i)
    if request.method == 'POST':
        addprioritylist = []
        for i in request.form:
            if not prioritizesearch.find_one({'_id':i}):
                prioritizesearch.insert_one({'_id':i,'date':datetime.utcnow()})
        return redirect(url_for('admin_console_page'))
    return render_template('management/prioritizearticles.html', allarticles=allarticles)

@app.route('/modsearch/seeprioritized', methods=['GET','POST'])
def search_see_prioritized_page():
    if not is_admin_loggedin():
        return redirect(url_for('home_page'))
    allprioritized = list(prioritizesearch.find())
    return render_template('management/viewprioritized.html',allprioritized=allprioritized)

@app.route('/visitormapview', methods=['GET','POST'])
def visitor_mapview_page():
    if not is_admin_loggedin():
        return redirect((url_for('home_page')))
    allipdata = list(ipdata.find())
    rawjson = '{ "type": "FeatureCollection","features": ['
    counter = 0
    for i in allipdata:
        counter +=1
        url = "https://look-for-ip.p.rapidapi.com/" + i.get('ip')
        headers = {
	        "X-RapidAPI-Key": constants.iplookuptoken ,
	        "X-RapidAPI-Host": "look-for-ip.p.rapidapi.com"
        }
        response = requests.request("GET", url, headers=headers).json()
        placeholder = '{{"type": "Feature","geometry": {{"type": "Point","coordinates": [{lon}, {lat}]}},"properties": {{"title": "{name}","description": "{description}"}}}}{comma}'
        if counter >= len(allipdata):
            rawjson += placeholder.format(lon=str(response['data']["longitude"]),lat=str(response['data']["latitude"]),name=response['data']['ip'],description=str(i.get("users_associated")),comma="")
        else:
            rawjson += placeholder.format(lon=str(response['data']["longitude"]),lat=str(response['data']["latitude"]),name=response['data']['ip'],description=str(i.get("users_associated")),comma=",")
    rawjson += ']}'
    #return rawjson
    return render_template('management/visitormapview.html',mapbox_access_token=constants.mapbox_access_token,longitude=0,latitude=0,mapdata=json.loads(rawjson))
    return json.loads(rawjson)

@app.route('/articles', methods=['GET', 'POST'])
def articles_page():
    allarticles = list(wikiarticles.find({"burned":False}))

    numarticles = len(allarticles)
    if numarticles <= 0:
        return "no pages are set up"
    return render_template('pagelist.html',articles=allarticles)

@app.route('/random', methods=['GET', 'POST'])
def random_page():
    allarticles = list(wikiarticles.find({"burned":False}))
    for article in allarticles:
        if article.get("publish") > datetime.utcnow():
            allarticles.remove(article)
    numarticles = len(allarticles)
    articleselected = random.randrange(numarticles)
    if numarticles <= 0:
        return "no pages are set up"
    return redirect('/page/' + allarticles[articleselected].get("_id"))

#to-do
@app.route('/pagenotfound')
def page_not_found():
    return "lol"


@app.route('/users', methods=['GET','POST'])
def users_page():
    if not is_admin_loggedin():
        return redirect(url_for('home_page'))
    userlist = list(users.find())
    return render_template('management/listusers.html',userlist=userlist)

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
            ipaddr = request.remote_addr
            if not ipdata.find_one({'ip':ipaddr}):
                ipdata.insert_one({'ip':ipaddr, 'users_associated':[username], 'timesloggedin':1,'dateactive':datetime.utcnow()})
            else:
                ip_data_associated = ipdata.find_one({'ip':ipaddr})
                users_associated = ip_data_associated.get('users_associated')
                if not username in users_associated:
                    users_associated.append(username)
                ipdata.update_one({'ip':ipaddr},{"$set":{'users_associated':users_associated,'timesloggedin':ip_data_associated.get('timesloggedin')+1,'dateactive':datetime.utcnow()}})
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
        is_admin = adminpassword == admindata.find_one({'_id':'adminpassword'}).get("password")
        users.insert_one({"username":username,"email":email,"password":password,"faction": "","profilepic":"", "bio": "", "is_admin": is_admin,"created":datetime.utcnow(),"lastlogin":datetime.utcnow(),"lastprofilechange":datetime.utcnow()})
        return redirect(url_for('login_page'))
    return render_template('session/register.html')

@app.route('/headline', methods=['GET','POST'])
def headline_page():
    if not is_admin_loggedin():
        return redirect(url_for('home_page'))
    if request.method == 'POST':
        newheadline = request.form.get("headline")
        admindata.update_one({'_id':'headline'},{"$set":{'headline':newheadline}})
        return redirect(url_for('headline_page'))
    return render_template('management/setheadline.html')

@app.route('/adminpassword', methods=['GET','POST'])
def adminpassword_page():
    if not is_admin_loggedin():
        return redirect(url_for('home_page'))
    passworddata = admindata.find_one({'_id':'adminpassword'})
    if request.method == 'POST':
        newadminpassword = request.form.get("adminpassword")
        admindata.update_one({'_id':'adminpassword'},{"$set":{"password":newadminpassword}})
        return redirect(url_for('adminpassword_page'))
    return render_template('management/setadminpassword.html', title="admin password", keyword=passworddata.get("password"))

@app.route('/mcserverip', methods=['GET','POST'])
def mcserverip_page():
    if not is_admin_loggedin():
        return redirect(url_for('home_page'))
    mcserveripdata = admindata.find_one({'_id':'mcserverip'})
    if request.method == 'POST':
        newmcserverip = request.form.get("adminpassword")
        admindata.update_one({'_id':'mcserverip'},{'$set':{'mcserverip':newmcserverip}})
        return redirect(url_for('mcserverip_page'))
    return render_template('management/setadminpassword.html', title="MC Server IP", keyword=mcserveripdata.get('mcserverip'))

@app.route('/featuredarticle', methods=['GET','POST'])
def featuredarticle_page():
    if not is_admin_loggedin():
        return redirect(url_for('home_page'))
    featuredarticledata = admindata.find_one({'_id':'featuredarticle'})
    if request.method == 'POST':
        newfeaturedarticledata = request.form.get("adminpassword")
        admindata.update_one({'_id':'featuredarticle'},{'$set':{'featuredarticle':newfeaturedarticledata}})
        return redirect(url_for('featuredarticle_page'))
    return render_template('management/setadminpassword.html', title="featured article", keyword=featuredarticledata.get('featuredarticle'))

@app.route('/tagslist', methods=['GET','POST'])
def tags_list_page():
    #do not show burn-on-read tags
    taglist= list(tagdata.find().sort('tag',pymongo.ASCENDING))
    for i in taglist:
        if i.get('tag') == 'burn-on-read':
            taglist.remove(i)
    return render_template('taglist.html', taglist=taglist)

@app.route('/tags', methods=['GET','POST'])
def tags_page():
    if not is_admin_loggedin():
        return redirect(url_for('home_page'))
    tagslist = list(tagdata.find())
    if request.method == 'POST':
        tagname = request.form.get("tagname")
        priority = int(request.form.get("priority"))
        datecreated = datetime.utcnow()
        selected = 'is-selected' in request.form
        comment = request.form.get("comment")
        if not tagdata.find_one({'tag':tagname}):
            tagdata.insert_one({'tag':tagname,'priority':priority,'datecreated': datecreated,'selected':selected,'comment':comment})
        else:
            return "tag already exists"
        return redirect(url_for('tags_page'))
    return render_template('management/tags.html',tagslist=tagslist)

@app.route('/tag/edit/<tagname>', methods=['GET','POST'])
def tag_edit_page(tagname):
    if not is_admin_loggedin():
        return redirect(url_for('home_page'))
    taginfo = tagdata.find_one({'tag':tagname})
    if not taginfo:
        return redirect(url_for('tags_page'))
    return render_template('management/taginfo.html',taginfo=taginfo)

@app.route('/tag/remove/<tagname>', methods=['GET','POST'])
def tag_remove_page(tagname):
    if not is_admin_loggedin():
        return redirect(url_for('home_page'))
    tagdata.delete_one({'tag':tagname})
    return redirect(url_for('tags_page'))

@app.route('/routelinks', methods=['GET','POST'])
def routes_page():
    if not is_admin_loggedin():
        return redirect(url_for('home_page'))
    links = list(linksdata.find())

    
    return render_template('management/links.html',links=links)

@app.route('/routelink/edit/<id>', methods=['GET','POST'])
def route_edit_page(id):
    if not is_admin_loggedin():
        return redirect(url_for('home_page'))
    routelink = linksdata.find_one({'_id':ObjectId(id)})
    if not routelink:
        return redirect(url_for('routes_page'))
    route = routelink.get("route")
    name = routelink.get("name")
    priority = routelink.get("priority")
    is_section_head = routelink.get("is_section_head")
    tag = routelink.get("tag")
    if request.method == 'POST':
        route = request.form.get("route")
        name = request.form.get("name")
        priority = request.form.get("priority")
        is_section_head = 'is-section-head' in request.form
        tag = request.form.get("tag")
        linksdata.update_one({'_id':ObjectId(id)},{"$set":{"route":route,"name":name,"priority":priority,"is_section_head":is_section_head,"tag":tag}})
        return redirect(url_for('routes_page'))
    return render_template('management/editlink.html',id=id,route=route,name=name,priority=priority,is_section_head=is_section_head,tag=tag)

@app.route('/routelink/add', methods=['GET','POST'])
def add_route_page():
    if not is_admin_loggedin():
        return redirect(url_for('home_page'))
    if request.method == 'POST':
        route = request.form.get("route")
        name = request.form.get("name")
        priority = request.form.get("priority")
        is_section_head = 'is-section-head' in request.form
        tag = request.form.get("tag")
        linksdata.insert_one({"route":route,"name":name,"priority":priority,"is_section_head":is_section_head,"tag":tag})
        return redirect(url_for('routes_page'))
    return render_template('management/editlink.html',id="New Route",route="",name="",priority=0,is_section_head=False,tag="")

@app.route('/setup', methods=['GET','POST'])
def setup_page():
    if not admindata.find_one({'_id':'adminpassword'}):
        site_setup()
        return "wesite set up success"
    return "website is already set up!"

@app.route('/logout', methods=['GET','POST'])
def logout():
    session['username'] = None
    return redirect(url_for('home_page'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port = 80)