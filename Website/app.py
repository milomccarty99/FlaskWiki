import flask
from flask import Flask, render_template, request, url_for, redirect, jsonify, flash, session
from flask_bootstrap import Bootstrap5
from pymongo import MongoClient
import requests
import datetime
import sys
import os.path
import json
import re
import secrets

import constants

app = flask.Flask(__name__)
bootsrtap = Bootstrap5(app)

mongoclient = MongoClient("mongodb://127.0.0.1:27017")


@app.route('/',methods=['GET','POST'])
def home_page():
    return "Hello World"

@app.route('/page/<id>', methods=['GET','POST'])
def site_page(id):
    return "Hello World " + str(id)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port = 80)