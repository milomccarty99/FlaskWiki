from pymongo import MongoClient

mongoclient = MongoClient('127.0.0.1', port=27017)


def help():
    return ""