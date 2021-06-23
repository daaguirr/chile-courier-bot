from playhouse.migrate import *

db = SqliteDatabase('database.db')
migrator = SqliteMigrator(db)

desc = CharField(null=True, default=None)

migrate(
    migrator.add_column('jobmodel', 'desc', desc),
)
