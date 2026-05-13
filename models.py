import datetime
from peewee import (
    SqliteDatabase, Model, AutoField, DateTimeField, DateField,
    FloatField, IntegerField, CharField, ForeignKeyField,
)

db = SqliteDatabase(None)


class BaseModel(Model):
    class Meta:
        database = db


class BacktestRun(BaseModel):
    id = AutoField()
    started_at = DateTimeField(default=datetime.datetime.now)
    period_start = DateField()
    period_end = DateField()
    india_starting_capital = FloatField()
    usa_starting_capital = FloatField()
    india_final_capital = FloatField(null=True)
    usa_final_capital = FloatField(null=True)
    india_total_trades = IntegerField(default=0)
    usa_total_trades = IntegerField(default=0)
    status = CharField(default="RUNNING")


class Trade(BaseModel):
    id = AutoField()
    run = ForeignKeyField(BacktestRun, backref="trades")
    date = DateField()
    market = CharField()
    symbol = CharField()
    bias = CharField()
    direction = CharField()
    or_high = FloatField()
    or_low = FloatField()
    entry = FloatField()
    sl = FloatField()
    target = FloatField()
    exit_price = FloatField()
    exit_reason = CharField()
    shares = IntegerField()
    risk_amount = FloatField()
    pnl = FloatField()
    pnl_pct = FloatField()
    capital_after = FloatField()


class DailyEquity(BaseModel):
    id = AutoField()
    run = ForeignKeyField(BacktestRun, backref="daily_equity")
    date = DateField()
    market = CharField()
    capital = FloatField()
    drawdown_pct = FloatField()
    trades_today = IntegerField()
    bias = CharField(null=True)


def initialize_db(db_path: str):
    db.init(db_path)
    db.connect()
    db.create_tables([BacktestRun, Trade, DailyEquity])
    return db
