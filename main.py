import json
import logging
import pathlib
from dataclasses import dataclass
from typing import Callable, Dict, Type

# noinspection PyPackageRequirements
import telegram.ext
# noinspection PyPackageRequirements
from tabulate import tabulate
from telegram import ReplyKeyboardRemove, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
# noinspection PyPackageRequirements
from telegram.ext import Updater, Job, ConversationHandler, CommandHandler, MessageHandler, Filters, \
    CallbackQueryHandler

# Enable logging
# noinspection PyUnresolvedReferences
from classes import RawDataScrapper, DevDataScrapper, BluexRaw, PullmanBusCargoRaw, StarkenRaw, ChileExpressRaw
import string
import random as rnd

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


@dataclass
class ListenCodeContext:
    chat_id: int
    currier: str
    code: str
    last_update: str = None


# noinspection PyUnusedLocal
def start(update: telegram.Update, context: telegram.ext.CallbackContext):
    """Send a message when the command /start is issued."""
    update.message.reply_text('Hi! I am Chile Courier Bot and i can listen your deliveries. \n'
                              'Supported Couriers: Chilexpress, Bluex, PullmanBusCargo, Starken \n'
                              'Posible Commands: \n'
                              '/subscribe : subscribe to a courier tracking with code \n'
                              '/shut_up : stop subscription \n'
                              '/subscriptions : list subscriptions'
                              )
    logger.info(update.message)  # INIT: host the bot , send a /start , add chat_id (on this log) to whitelist


# noinspection PyUnusedLocal,PyShadowingBuiltins
def help(update: telegram.Update, context: telegram.ext.CallbackContext):
    """Send a message when the command /help is issued."""
    update.message.reply_text('Posible Commands: \n'
                              '/subscribe : subscribe to a courier tracking with code \n'
                              '/shut_up : stop subscription \n'
                              '/subscriptions : list subscriptions \n'
                              'Supported Couriers: Chilexpress, Bluex, PullmanBusCargo, Starken')


# noinspection PyUnusedLocal,PyShadowingNames
def error(update: telegram.Update, context: telegram.ext.CallbackContext):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


# noinspection PyUnusedLocal
def cancel(update: telegram.Update, context: telegram.ext.CallbackContext):
    user = update.message.from_user
    logger.info("User %s canceled", user.first_name)
    update.message.reply_text('Canceled',
                              reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def generate_key():
    return ''.join([rnd.choice(alphabet) for _ in range(8)])


def register_job(job_fn: Callable[[str], Job], context: telegram.ext.CallbackContext) -> str:
    current_jobs = {**context.user_data['jobs']} if 'jobs' in context.user_data else {}

    key = generate_key()
    while key in current_jobs:
        key = generate_key()

    job = job_fn(str(key))
    current_jobs[str(key)] = job
    context.user_data['jobs'] = current_jobs
    return str(key)


def cancel_job(name: str, context: telegram.ext.CallbackContext) -> bool:
    current_jobs = {**context.user_data['jobs']} if 'jobs' in context.user_data else {}
    if name not in current_jobs:
        return False
    job: Job = current_jobs[name]
    job.schedule_removal()  # TODO: check if job is already terminated
    del current_jobs[name]  # WARNING: delete on job queue on next check
    return True


# noinspection PyUnusedLocal
def shut_up(update: telegram.Update, context: telegram.ext.CallbackContext):
    update.message.reply_text('Please enter name of listener to finish or /cancel', reply_markup=ReplyKeyboardRemove())
    return JOB_CANCEL


def shut_up_get_job_name(update: telegram.Update, context: telegram.ext.CallbackContext):
    name = str(update.message.text)
    val = cancel_job(name, context)
    msg = f'Finished listener with name = {name}' if val else f'Error in finish job with name {name} '
    context.bot.send_message(chat_id=update.message.chat_id,
                             text=msg)
    return ConversationHandler.END


def get_subscriptions(update: telegram.Update, context: telegram.ext.CallbackContext):
    current_jobs = {**context.user_data['jobs']} if 'jobs' in context.user_data else {}
    table = []
    for name, job in current_jobs.items():
        table.append([name, f"{job.context.currier.upper()} {job.context.code}"])
    table_formatted = tabulate(table, headers=["Name", "Courier code"], tablefmt="github")
    update.message.reply_html(f"<pre>{table_formatted}</pre>")
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

    del context.user_data['currier']
    del context.user_data['delta']

    def listen_currier_job_fn(name: str):
        return context.job_queue.run_repeating(check_update,
                                               interval=delta, first=0,
                                               context=ListenCodeContext(update.message.chat_id, currier,
                                                                         code),
                                               name=name)

    name_job = register_job(listen_currier_job_fn, context)
    context.bot.send_message(chat_id=update.message.chat_id,
                             text=f'Starting listen {currier.upper()} {code} with name {name_job}')
    return ConversationHandler.END


def get_data(data: ListenCodeContext, context: telegram.ext.CallbackContext):
    currier = data.currier
    cod = data.code
    scrapper = dispatcher[currier]
    instance = scrapper(cod)
    try:
        new_data = instance.get_data()
    except Exception as e:
        context.bot.send_message(chat_id=data.chat_id,
                                 text=f"Error happening when trying to get data from {currier.upper()} {cod}")
        context.bot.send_message(chat_id=data.chat_id,
                                 text="This would be a invalid code, expired code or courier page error")
        logger.error(e)
        new_data = "ERROR"
    return new_data


def check_update(context: telegram.ext.CallbackContext):
    job: Job = context.job
    data: ListenCodeContext = job.context

    last_update = data.last_update
    currier = data.currier
    cod = data.code
    new_data = get_data(data, context)

    if new_data != last_update:
        context.bot.send_message(chat_id=data.chat_id,
                                 text=f'{currier.upper()} {cod} changed from:\n{last_update} to {new_data}')
        context.job.context.last_update = new_data


def force_get(update: telegram.Update, context: telegram.ext.CallbackContext):
    current_jobs = {**context.user_data['jobs']} if 'jobs' in context.user_data else {}
    keys = {k: f"{j.context.currier.upper()} {j.context.code}" for k, j in current_jobs.items()}
    markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton(text=value,
                               callback_data=key)] for key, value in keys.items()]
    )

    update.message.reply_text('Please select job or /cancel',
                              reply_markup=markup)
    return SELECT_JOB


def select_job(update: telegram.Update, context: telegram.ext.CallbackContext):
    key = update.callback_query.data
    current_jobs = {**context.user_data['jobs']} if 'jobs' in context.user_data else {}
    job: Job = current_jobs[key]
    new_data = get_data(data=job.context, context=context)
    if new_data != job.context.last_update:
        job.context.last_update = new_data
    update.effective_message.edit_text(f'{job.context.currier.upper()} {job.context.code} has state {new_data}')
    return ConversationHandler.END


def main():
    """Start the bot."""
    # Create the EventHandler and pass it your bot's token.
    updater = Updater(config["BOT_KEY"], use_context=True)
    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(CommandHandler("subscriptions", get_subscriptions))
    shut_up_hand = ConversationHandler(
        entry_points=[CommandHandler('shut_up', shut_up)],

        states={
            JOB_CANCEL: [MessageHandler(Filters.text & ~Filters.command, shut_up_get_job_name)],

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
