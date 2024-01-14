import asyncio
import logging
import sys
import os
import requests
from itertools import islice
from user import User
import convertapi
from bs4 import BeautifulSoup, Tag
from text_analysis import post_request
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command, Text
from aiogram.types import BotCommand, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

load_dotenv()
bot = Bot(token=os.getenv('BOT_TOKEN'))
router = Router()

users = {}
WAIT_FOR = None
TEXTS = {
    'start': 'Привет! Я - бот по тренировке памяти через пересказ текста наизусть. Ну что, начнём?',
    'not_a_new_user': 'Нет нет. Ты уже не новичок.',
    'info': 'Данный бот предназначен для тренировки памяти. Вам даётся текст определённой длины,'
            ' потом текст исчезает и ваша задача - постараться пересказать текст как можно точнее.'
            ' Далее бот выведет уровень совпадения вашего пересказа с оригинальным текстом.\nТаким'
            ' образом ваш мозг учится быстро запоминать массивы текста.',
    'introduction': 'Итак, позволь мне рассказать, как я работаю и что мы с тобой будем делать. '
                    'Я тебе буду показывать отрывки текстов, а ты мне их будешь пересказывать как'
                    ' можно точнее. Как только ты нажмёшь кнопку "Начать", '
                    'начни вводить пересказ увиденного текста\n\nДавай опробуем разочек.',
    'retelling_result': 'Отлично! Оценка твоего пересказа: {0} из 100.\nВот сравнение ответа с исходником:',
    'set_preferences': 'Ну как? Насколько тебе было удобно с таким текстом? Может он был слишком '
                       'большим и неподъёмным для тебя или наоборот, слишком коротким.\n\nНапиши, '
                       'какой длины текст (в словах) тебе подходит больше всего?\n(Текст сверху 30 слов в длину)',
    'change_text_length': 'Укажите предпочитаемую длину текста:',
    'account': 'Создан: {0}\nКол-во пересказов {1}\nСредняя оценка: {2}\nДлина текстов в словах: {3}',
    'preferences_saved': 'Хорошо, я сохранил твоё предпочтение. Теперь тексты будут ровно такой длины. Если что,'
                         ' эту настройку всегда можно поменять в меню.',
    'main_menu': 'Вот о чём мы можем поговорить:',
    'parting': 'Пока!',
    'settings': 'Настройки'
}

def batched(iterable, n):  # аналог batched из itertools для python 3.12
    i = iter(iterable)
    piece = list(islice(i, n))
    while piece:
        yield ' '.join(piece)
        piece = list(islice(i, n))


class ParseContent:
    def get_content(self, user):
        def get_content(soup):
            if user.preferred_text_length:
                chunk_size = user.preferred_text_length
            else:
                chunk_size = 30

            extra_classes = ('caption', 'credit')  # ненужные классы

            item = soup.find('div', class_='free-content')
            paragraphs = item.find_all('p', class_=lambda c: c not in extra_classes)

            words = ' '.join(map(Tag.get_text, paragraphs)).split()  # разбиение текста на слова
            chunks = list(batched(words, chunk_size))  # разбиение текста на куски по 30 слов
            if len(chunks[-1]) < chunk_size * 3:
                # добавляем текст последней статьи к предпоследней если в ней слишком мало слов
                chunks[-1] = chunks[-2] + chunks.pop()

            return chunks

        main_page_html = self.get_html('https://republic.ru')
        main_page_soup = BeautifulSoup(main_page_html.text, 'html.parser')
        curr_post_id = self.get_last_article(main_page_soup)

        while curr_post_id in user.seen_ids:
            curr_post_id -= 1

        article_url = f'https://republic.ru/posts/{curr_post_id}'
        article_html = self.get_html(article_url)
        article_soup = BeautifulSoup(article_html.text, 'html.parser')

        user.seen_ids.append(curr_post_id)

        return get_content(article_soup)

    @staticmethod
    def get_html(url):
        return requests.get(url, headers={'User-Agent': 'Chrome'}, verify=False)

    @staticmethod
    def get_last_article(soup):  # получение id последней статьи
        items = soup.find('a', class_='card__link').get('href')
        last_post = int(items.replace('/posts/', ''))

        return last_post


parse_content = ParseContent()


@router.message(Command('start'))
async def command_start(message):
    global users

    if users.get(message.from_user.id):
        await message.answer(TEXTS['not_a_new_user'])
        await main_menu(message)
    else:
        users[message.from_user.id] = User(message.from_user.id)

        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text='Поехали!!', callback_data='introduction'))

        await message.answer(TEXTS['start'], reply_markup=builder.as_markup())


@router.message(Command('menu'))
async def main_menu(message):
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text='Настройки', callback_data='open_settings'))
    builder.add(InlineKeyboardButton(text='Начать практику', callback_data='start_reciting'))
    builder.add(InlineKeyboardButton(text='Пока!', callback_data='parting'))

    await message.answer(TEXTS['main_menu'], reply_markup=builder.as_markup())


@router.message(Command('info'))
async def command_info(message):
    await message.answer(TEXTS['info'])


@router.callback_query(Text('introduction'))
async def introduction(callback):
    await bot.edit_message_reply_markup(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        reply_markup=None)

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text='Давай', callback_data='start_reciting'))

    await callback.message.answer(TEXTS['introduction'], reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(Text('start_reciting'))
async def reciting(callback):
    user = users[callback.from_user.id]

    await bot.edit_message_reply_markup(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        reply_markup=None)

    if not user.current_title:
        user.current_title = parse_content.get_content(user)

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text='Начать', callback_data='check_result'))

    await callback.message.answer(user.current_title[0], reply_markup=builder.as_markup())


@router.callback_query(Text('check_result'))
async def settings(callback):
    global WAIT_FOR

    WAIT_FOR = 'retelling_result'

    await bot.delete_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id)


async def after_retelling(message, score):
    global WAIT_FOR

    user = users[message.from_user.id]
    user.completed_retellings += 1
    user.scores.append(score)

    if user.preferred_text_length:
        await main_menu(message)
    else:
        WAIT_FOR = 'preferences_saved'
        await message.answer(TEXTS['set_preferences'])


@router.callback_query(Text('parting'))
async def parting(callback):
    await bot.edit_message_reply_markup(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        reply_markup=None)

    await callback.message.answer(TEXTS['parting'])


@router.callback_query(Text('open_settings'))
async def settings(callback):
    await bot.edit_message_reply_markup(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        reply_markup=None)

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text='Поменять длину текстов', callback_data='change_text_length'))
    builder.add(InlineKeyboardButton(text='Аккаунт', callback_data='account'))

    builder.adjust(1)

    await callback.message.answer(TEXTS['settings'], reply_markup=builder.as_markup())


@router.callback_query(Text('change_text_length'))
async def parting(callback):
    global WAIT_FOR
    WAIT_FOR = 'preferences_saved'

    await bot.edit_message_reply_markup(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        reply_markup=None)

    await callback.message.answer(TEXTS['change_text_length'])


@router.callback_query(Text('account'))
async def parting(callback):
    await bot.edit_message_reply_markup(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        reply_markup=None)

    user = users[callback.from_user.id]
    users_data = user.reg_date, user.completed_retellings, user.get_average_score(), user.preferred_text_length

    await callback.message.answer(TEXTS['account'].format(*users_data))


@router.message()
async def random_message(message):
    global WAIT_FOR, users

    user = users[message.from_user.id]

    if WAIT_FOR == 'retelling_result':
        WAIT_FOR = None

        html_comparison, score = post_request(message.text, user.current_title.pop(0))
        file = open('comp.html', 'w', encoding='utf-8')
        file.write(html_comparison)
        file.close()

        convertapi.api_secret = 'vJv2fvONA1zRPjad'
        png_comp = convertapi.convert('png', {'File': 'comp.html'}, from_format='html')

        await message.answer(TEXTS['retelling_result'].format(score))
        await bot.send_photo(message.from_user.id, png_comp.file.url)
        await after_retelling(message, score)
    elif WAIT_FOR == 'preferences_saved':
        if message.text.isdigit():
            preferred_text_length = max(10, min(1500, int(message.text)))
            user.current_title = None
        else:
            preferred_text_length = 30

        user.preferred_text_length = preferred_text_length

        WAIT_FOR = None

        await message.answer(TEXTS['preferences_saved'])
        await main_menu(message)
    else:
        await main_menu(message)


async def main():
    dp = Dispatcher()
    dp.include_router(router)

    commands = [
        BotCommand(command="/start", description="Start conversation"),
        BotCommand(command="/info", description="More information about bot"),
        BotCommand(command="/menu", description="Main menu")
    ]

    await bot.set_my_commands(commands)
    await dp.start_polling(bot)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
