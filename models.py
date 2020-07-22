from peewee import *

db = SqliteDatabase('database.db')


class BaseModel(Model):
    class Meta:
        database = db


class JobModel(BaseModel):
    id = CharField(unique=True)
    name = CharField()
    chat_id = CharField()
    delta = CharField()
    courier = CharField()
    cod = CharField()
    last_update = CharField(null=True)


if __name__ == '__main__':
    db.connect()
    db.create_tables([JobModel])
