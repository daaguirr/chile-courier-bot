import json
import logging
import pathlib
import random as rnd
import string
import uuid
from typing import Callable, Dict, Type, Iterator, Optional, Tuple

# noinspection PyPackageRequirements
import telegram.ext
# noinspection PyPackageRequirements
# noinspection PyPackageRequirements
from telegram import ReplyKeyboardRemove, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
# noinspection PyPackageRequirements
from telegram.ext import Updater, Job, ConversationHandler, CommandHandler, MessageHandler, Filters, \
    CallbackQueryHandler

# Enable logging
# noinspection PyUnresolvedReferences
from classes import RawDataScrapper, DevDataScrapper, BluexRaw, PullmanBusCargoRaw, StarkenRaw, ChileExpressRaw
from models import JobModel
from tables import generate_image

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

alphabet = string.ascii_uppercase + string.digits

logger = logging.getLogger(__name__)

path = pathlib.Path(__file__).parent.absolute()

with open(path.joinpath('config.json'), 'r') as f:
    config = json.load(f)

SELECT_CURRIER, SELECT_TIME, SELECT_CODE, JOB_CANCEL, SELECT_JOB = range(5)

time_dict = {
    "1min": 60,
    "5min": 300,
    "1hr": 3600,
    "12hr": 12 * 3600,
    "24hr": 24 * 3600
}

keyboard_time_keyboard = [[k] for k in time_dict.keys()]
time_regex = f"^({'|'.join(time_dict.keys())})$"

if config["DEV"]:
    dispatcher: Dict[str, Type[RawDataScrapper]] = {
        'develop': lambda code: DevDataScrapper(code)
    }
else:
    dispatcher: Dict[str, Type[RawDataScrapper]] = {
        'Chilexpress': lambda code: ChileExpressRaw(code),
        'Bluex': lambda code: BluexRaw(code),
        'PullmanBusCargo': lambda code: PullmanBusCargoRaw(code),
        'Starken': lambda code: StarkenRaw(code),

    }
keyboard_currier_keyboard = [[k] for k in dispatcher.keys()]
currier_regex = f"^({'|'.join(dispatcher.keys())})$"


# noinspection PyUnusedLocal
def start(update: telegram.Update, context: telegram.ext.CallbackContext):
    """Send a message when the command /start is issued."""
    update.message.reply_text('Hi! I am Chile Courier Bot and i can listen your deliveries. \n'
                              'Supported Couriers: Chilexpress, Bluex, PullmanBusCargo, Starken \n'
                              'Posible Commands: \n'
                              '/subscribe : subscribe to a courier tracking with code \n'
                              '/shut_up : stop subscription \n'
                              '/subscriptions : list subscriptions\n'
                              '/force_get : get current state of tracking'
                              )
    logger.info(update.message)  # INIT: host the bot , send a /start , add chat_id (on this log) to whitelist


# noinspection PyUnusedLocal,PyShadowingBuiltins
def help(update: telegram.Update, context: telegram.ext.CallbackContext):
    """Send a message when the command /help is issued."""
    update.message.reply_text('Posible Commands: \n'
                              '/subscribe : subscribe to a courier tracking with code \n'
                              '/shut_up : stop subscription \n'
                              '/subscriptions : list subscriptions \n'
                              '/force_get : get current state of tracking \n'
                              'Supported Couriers: Chilexpress, Bluex, PullmanBusCargo, Starken')


# noinspection PyUnusedLocal,PyShadowingNames
def error(update: telegram.Update, context: telegram.ext.CallbackContext):
    """Log Errors caused by Updates."""
    import traceback
    logger.error('Update "%s" caused error "%s" \n "%s"', update, context.error, traceback.print_exc())


# noinspection PyUnusedLocal
def cancel(update: telegram.Update, context: telegram.ext.CallbackContext):
    user = update.message.from_user
    logger.info("User %s canceled", user.first_name)
    update.message.reply_text('Canceled',
                              reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def generate_key():
    return ''.join([rnd.choice(alphabet) for _ in range(8)])


def get_current_jobs(chat_id):
    return JobModel.select().where(JobModel.chat_id == chat_id)


def register_job(job_fn: Callable[[str], Job], update: telegram.Update, delta, courier, code) -> str:
    current_jobs = get_current_jobs(chat_id=update.message.chat_id)
    keys = [j.name for j in current_jobs]
    key = generate_key()
    while key in keys:
        key = generate_key()

    job_db = JobModel.create(id=str(uuid.uuid4()),
                             name=key,
                             chat_id=update.message.chat_id,
                             delta=delta,
                             courier=courier,
                             cod=code,
                             last_update=None)
    job_db.save()
    job_fn(str(key))

    return str(key)


def cancel_job(name: str, update: telegram.Update, context: telegram.ext.CallbackContext) -> Tuple[bool, Optional[str]]:
    job = context.job_queue.get_jobs_by_name(name)
    if len(job) == 0:
        return False, None

    job[0].schedule_removal()  # TODO: check if job is already terminated
    job_db: JobModel = JobModel.get(JobModel.chat_id == update.effective_message.chat_id, JobModel.name == name)
    key = f"{job_db.courier.upper()} {job_db.cod}"
    job_db.delete_instance()
    return True, key


def get_jobs_inline(update: telegram.Update):
    current_jobs: Iterator[JobModel] = get_current_jobs(update.message.chat_id)
    markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton(text=f"{j.courier.upper()} {j.cod}",
                               callback_data=j.name)] for j in current_jobs])

    update.message.reply_text('Please select job or /cancel',
                              reply_markup=markup)


# noinspection PyUnusedLocal
def shut_up(update: telegram.Update, context: telegram.ext.CallbackContext):
    get_jobs_inline(update)
    return JOB_CANCEL


def shut_up_get_job_name(update: telegram.Update, context: telegram.ext.CallbackContext):
    name = update.callback_query.data
    val, key = cancel_job(name, update, context)
    msg = f'Finished listener for {key}' if val else f'Error in finish job {key} '
    update.effective_message.edit_text(msg)
    return ConversationHandler.END


# noinspection PyUnusedLocal
def get_subscriptions(update: telegram.Update, context: telegram.ext.CallbackContext):
    current_jobs: Iterator[JobModel] = get_current_jobs(update.message.chat_id)
    table = []
    for job in current_jobs:
        table.append([job.courier.upper(), job.cod])

    table_image = generate_image(table, columns=['Courier 🚚', 'Code 🔑'])
    print(table)
    update.message.reply_photo(table_image)
    return ConversationHandler.END


# noinspection PyUnusedLocal
def subscribe(update: telegram.Update, context: telegram.ext.CallbackContext):
    update.message.reply_text(text=f"Please enter currier",
                              reply_markup=ReplyKeyboardMarkup(keyboard_currier_keyboard, one_time_keyboard=True))
    return SELECT_CURRIER


def select_currier(update: telegram.Update, context: telegram.ext.CallbackContext):
    context.user_data['currier'] = update.message.text
    update.message.reply_text('Please enter refresh time or /cancel',
                              reply_markup=ReplyKeyboardMarkup(keyboard_time_keyboard, one_time_keyboard=True))
    return SELECT_TIME


def select_time(update: telegram.Update, context: telegram.ext.CallbackContext):
    time_text = update.message.text
    time = time_dict[time_text]
    context.user_data['delta'] = time
    update.message.reply_text('Please enter tracking code to listen or /cancel', reply_markup=ReplyKeyboardRemove())
    return SELECT_CODE


def select_code(update: telegram.Update, context: telegram.ext.CallbackContext):
    code: str = update.message.text
    delta = context.user_data['delta']
    currier: str = context.user_data['currier']
    chat_id: str = update.message.chat_id

    del context.user_data['currier']
    del context.user_data['delta']

    def listen_currier_job_fn(name: str):
        return context.job_queue.run_repeating(check_update,
                                               interval=delta,
                                               first=0,
                                               context={"chat_id": chat_id, "name": name},
                                               name=name)

    register_job(listen_currier_job_fn, update, delta, currier, code)

    context.bot.send_message(chat_id=update.message.chat_id,
                             text=f'Starting listen {currier.upper()} {code}')
    return ConversationHandler.END


def get_data(job: JobModel, context: telegram.ext.CallbackContext):
    currier = job.courier
    cod = job.cod
    scrapper: Type[RawDataScrapper] = dispatcher[currier]
    instance = scrapper(cod)
    try:
        new_data = instance.get_data()
    except Exception as e:
        context.bot.send_message(chat_id=job.chat_id,
                                 text=f"Error happening when trying to get data from {currier.upper()} {cod}")
        context.bot.send_message(chat_id=job.chat_id,
                                 text="This would be a invalid code, expired code or courier page error")
        logger.error(e)
        new_data = "ERROR"
    return new_data


def check_update(context: telegram.ext.CallbackContext):
    job: Job = context.job
    data = job.context
    job_db: JobModel = JobModel.get(JobModel.chat_id == data["chat_id"], JobModel.name == data["name"])

    last_update = job_db.last_update
    currier = job_db.courier
    cod = job_db.cod
    new_data = get_data(job_db, context)

    if new_data != last_update:
        context.bot.send_message(chat_id=data["chat_id"],
                                 text=f'*UPDATED*: {currier.upper()} {cod}\n*FROM*: '
                                      f'{last_update.upper()}\n*TO*: {new_data.upper()}',
                                 parse_mode=telegram.ParseMode.MARKDOWN
                                 )
        job_db.last_update = new_data
        job_db.save()


# noinspection PyUnusedLocal
def force_get(update: telegram.Update, context: telegram.ext.CallbackContext):
    get_jobs_inline(update)
    return SELECT_JOB


def select_job(update: telegram.Update, context: telegram.ext.CallbackContext):
    key = update.callback_query.data
    job: JobModel = JobModel.get(JobModel.chat_id == update.effective_message.chat_id, JobModel.name == key)
    new_data = get_data(job=job, context=context)
    if new_data != job.last_update:
        job.last_update = new_data
        job.save()
    update.effective_message.edit_text(f'{job.courier.upper()} {job.cod} has state:\n{new_data}')
    return ConversationHandler.END


def main():
    """Start the bot."""
    # Create the EventHandler and pass it your bot's token.
    updater = Updater(config["BOT_KEY"], use_context=True)
    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    for j in JobModel.select():
        print(j)
        updater.job_queue.run_repeating(
            check_update,
            interval=int(j.delta), first=0,
            context={"chat_id": j.chat_id, "name": j.name},
            name=j.name
        )

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(CommandHandler("subscriptions", get_subscriptions))
    shut_up_hand = ConversationHandler(
        entry_points=[CommandHandler('shut_up', shut_up)],

        states={
            JOB_CANCEL: [CallbackQueryHandler(shut_up_get_job_name, pass_user_data=True)],

        },

        fallbacks=[CommandHandler('cancel', cancel)]
    )
    dp.add_handler(shut_up_hand)

    subs_handler = ConversationHandler(
        entry_points=[CommandHandler('subscribe', subscribe)],

        states={
            SELECT_CURRIER: [MessageHandler(Filters.regex(currier_regex), select_currier)],
            SELECT_TIME: [MessageHandler(Filters.regex(time_regex), select_time)],
            SELECT_CODE: [MessageHandler(Filters.text & ~Filters.command, select_code)]
        },

        fallbacks=[CommandHandler('cancel', cancel)]
    )
    dp.add_handler(subs_handler)

    force_get_hand = ConversationHandler(
        entry_points=[CommandHandler('force_get', force_get)],

        states={
            SELECT_JOB: [CallbackQueryHandler(select_job, pass_user_data=True)],
        },

        fallbacks=[CommandHandler('cancel', cancel)]
    )
    dp.add_handler(force_get_hand)
    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
