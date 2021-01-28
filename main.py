import os
import re
import sqlite3
import sys
import textwrap
import uuid
from asyncio import get_event_loop
from configparser import ConfigParser
from hashlib import md5
from random import randint
from time import time

from pyrogram import Client, filters
from pyrogram.errors import WebpageCurlFailed
from pyrogram.types import Message, ChatPermissions
from pytube import YouTube
from requests import get

print('Initializing Things, Please Wait A Few Seconds!')
app = Client('testing')
parser = ConfigParser()
parser.read(str(app.config_file))
config_error = False
config_text = '''[FireScript-@userbot]
;Admin UserID:
bot_owner = 123456789
;Bot License Url
license_url = https://example.com/path/to/file.txt'''
if parser.has_section('FireScript-@userbot'):
    if parser.has_option('FireScript-@userbot', 'bot_owner'):
        bot_owner = int(parser.get('FireScript-@userbot', 'bot_owner'))
    else:
        parser.set("FireScript-@userbot", 'bot_owner', '123456789')
        raise AttributeError(
            '''Unable to find "bot_owner" option in "FireScript-@userbot" section, add following lines to config.ini\
             file:\n''' + config_text)
    if parser.has_option('FireScript-@userbot', 'license_url'):
        license_url = str(parser.get('FireScript-@userbot', 'license_url'))
    else:
        parser.set("FireScript-@userbot", 'license_url', 'https://example.com/path/to/file.txt')
        raise AttributeError(
            '''Unable to find "license_url" option in "FireScript-@userbot" section, add following lines to config.ini\
             file:\n''' + config_text)
else:
    parser.add_section("FireScript-@userbot")
    raise AttributeError('''Unable to find "FireScript-@userbot" section in "config.ini" file, add following lines to\
     config.ini file:\n''' + config_text)


class LicenseError(Exception):
    pass


if license_url != 'https://example.com/path/to/file.txt':
    try:
        license_content = get(license_url).json()
    except:
        raise LicenseError('License url/contents is invalid')
    my_license = '-'.join(textwrap.fill(md5(
        bytes((':'.join(['{:02x}'.format((uuid.getnode() >> ele) & 0xff) for ele in range(0, 8 * 6, 8)][::-1])),
              'utf-8')).hexdigest(), 4).split('\n'))
    if my_license in license_content:
        pass
    else:
        raise LicenseError(
            f'Your client is not authenticated to use this script, give following key to script\'s owner:\n{my_license}')
else:
    raise LicenseError('License url is invalid')
db = sqlite3.connect('testing.db', isolation_level=None, check_same_thread=False)
db_mem = sqlite3.connect(':memory:', isolation_level=None, check_same_thread=False)
db_mem.execute('CREATE TABLE IF NOT EXISTS floods ('
               '`identity` VARCHAR UNIQUE NOT NULL,'
               '`count` INTEGER NOT NULL DEFAULT 1,'
               '`last_check` INTEGER NOT NULL DEFAULT 0'
               ')')
cursor = db.cursor()
loop = get_event_loop()
cursor.execute('CREATE TABLE IF NOT EXISTS words ('
               '`word` VARCHAR UNIQUE NOT NULL,'
               '`answer` VARCHAR NOT NULL,'
               '`added` DATETIME DEFAULT current_timestamp NOT NULL'
               ')')
cursor.execute('CREATE TABLE IF NOT EXISTS admins ('
               '`userid` VARCHAR UNIQUE NOT NULL,'
               '`username` VARCHAR NULL,'
               '`first_name` VARCHAR NOT NULL,'
               '`added` DATETIME DEFAULT current_timestamp NOT NULL'
               ')')
cursor.execute('CREATE TABLE IF NOT EXISTS users ('
               '`userid` VARCHAR UNIQUE NOT NULL,'
               '`username` VARCHAR NULL,'
               '`first_name` VARCHAR NOT NULL,'
               '`private` BOOLEAN NOT NULL DEFAULT FALSE,'
               '`warned` BOOLEAN NOT NULL DEFAULT FALSE,'
               '`blocked` BOOLEAN NOT NULL DEFAULT FALSE,'
               '`added` DATETIME DEFAULT current_timestamp NOT NULL'
               ')')
cursor.execute('CREATE TABLE IF NOT EXISTS rose_messages ('
               '`chat_id` int NOT NULL,'
               '`message_id` int Not NULL,'
               '`rose_message_id` int NOT NULL,'
               '`added` DATETIME DEFAULT current_timestamp NOT NULL'
               ')')
cursor.execute('CREATE TABLE IF NOT EXISTS abuse_words ('
               '`word` VARCHAR UNIQUE NOT NULL,'
               '`added` DATETIME DEFAULT current_timestamp NOT NULL'
               ')')


class MyValues:
    def __init__(self, value: int):
        self.value = value

    def get_value(self) -> int:
        return self.value

    def set_value(self, value: int):
        self.value = value


async def check_admin(_, __, message: Message) -> bool:
    try:
        if message.from_user.id is None:
            return False
    except AttributeError:
        return False
    result = await loop.run_in_executor(None, db.cursor().execute(
        'SELECT userid FROM admins WHERE userid = ?', [message.from_user.id]).fetchone)
    return await check_owner(_, _, message) or result is not None and any(result)


async def check_user(*args) -> bool:
    return not await check_admin(*args)


async def check_owner(_, __, message: Message) -> bool:
    return bool(message.from_user.id) and message.from_user.id == bot_owner


async def check_word_answer(_, __, message: Message) -> bool:
    result = await loop.run_in_executor(None, db.cursor().execute('SELECT answer FROM words WHERE word = ?',
                                                                  [message.text]).fetchone)
    if result is None:
        return False
    return any(result)


async def check_insult(_, __, message: Message) -> bool:
    if await check_admin(_, __, message):
        return False
    if message.text is None:
        return False
    string = "%\' OR word LIKE \'%"
    result = await loop.run_in_executor(None, db.cursor().execute(
        f'SELECT word FROM abuse_words WHERE LOWER(word) LIKE \'%{string.join(message.text.lower().split(" "))}%\';').fetchone)
    if result is None:
        return False
    return any(result)


async def check_spam(_, __, message: Message) -> bool:
    if await check_admin(_, __, message):
        return False
    if await check_insult(_, __, message):
        return True
    try:
        string = f'{message.chat.id}:{message.from_user.id}'
    except:
        string = 'alsdkjflasdkjf'
    result = await loop.run_in_executor(None, db_mem.execute(
        f"SELECT count FROM floods WHERE identity = '{string}'").fetchone)
    if result is not None and any(result):
        if result[0] > 5:
            result = await loop.run_in_executor(None, db.execute(
                f"SELECT warned FROM users WHERE userid = '{message.from_user.id}'").fetchone)
            if result is not None and result[0] is True:
                return True
            else:
                await message.reply('**WARNING:\nI AM GOING TO BLOCK YOU! STOP FLOODING OR I WILL BLOCK YOU**')
                await loop.run_in_executor(None, db.execute, 'UPDATE users SET warned = TRUE WHERE userid = ?',
                                           [message.from_user.id])
    return False


async def check_block(_, __, message: Message) -> bool:
    try:
        if message.from_user.id is None:
            return False
    except AttributeError:
        return False
    result = await loop.run_in_executor(None, db.cursor().execute(
        'SELECT userid FROM users WHERE userid = ? AND blocked = TRUE', [message.from_user.id]).fetchone)
    return result is not None and any(result)


async def check_first_time(_, __, message: Message) -> bool:
    if await check_admin(_, __, message):
        return False
    try:
        if message.from_user.id is None:
            return False
    except AttributeError:
        return False
    result = await loop.run_in_executor(None, db.cursor().execute(
        'SELECT private FROM users WHERE userid = ?', [message.from_user.id]).fetchone)
    return result is None or not result[0]


async def progress_handler(current: int, total: int, message: Message, current_time: int, last_time: MyValues):
    pass
    # percent = round(current / total * 100)
    # if (current_time - last_time.get_value()) <= 3:
    #     return
    # try:
    #     await message.edit(f'''**Sending Video**
    # **Progress:** `{percent}%`''')
    # except:
    #     pass
    # last_time.set_value(current_time)


async def flood_handler(message: Message):
    await loop.run_in_executor(
        None, db_mem.execute,
        f"INSERT INTO floods (identity, count, last_check) "
        f"VALUES ('{message.chat.id}:{message.from_user.id}', 1, ?) "
        f"ON CONFLICT(identity) DO UPDATE SET count = count + 1", [round(time())])
    await flood_checker(message)


async def flood_checker(message: Message):
    string = f'{message.chat.id}:{message.from_user.id}'
    result = await loop.run_in_executor(None, db_mem.execute(
        f"SELECT last_check FROM floods WHERE identity = '{string}'").fetchone)
    if result is not None and round(time()) - result[0] > 20:
        await flood_cleaner(message)
    else:
        await loop.run_in_executor(None, db_mem.execute, 'UPDATE floods SET last_check = ? WHERE identity = ?',
                                   [round(time()), string])


async def flood_cleaner(message: Message):
    string = f'{message.chat.id}:{message.from_user.id}'
    await loop.run_in_executor(None, db_mem.execute, 'DELETE FROM floods WHERE identity = ?', [string])


def cc_gen():
    prefix = [526474, 530048, 557919]
    valid = prefix[randint(0, len(prefix) - 1)]

    newcard = list(map(int, str(valid)))

    for i in range(9):
        newcard.append(randint(0, 9))

    gen = list(newcard)
    gen.reverse()
    for i, x in zip(list(range(len(gen))), gen):
        if i % 2 == 0:
            dub = x * 2
            dub = dub / 10 + dub % 10
            gen[i] = dub

    check = sum(gen) * 9 % 10
    newcard.append(check)

    output = list(map(str, newcard))
    month = str(randint(1, 12))
    if len(month) == 1:
        month = f'0{month}'
    year = str(2021 + randint(0, 4))
    cvv = str(randint(453, 668))
    return [''.join(output).split('.')[0], month, year, cvv]


def cc_check(card_num):
    number = str(card_num).replace(' ', '')
    if len(number) < 2 or re.findall(r"\D", number):
        return False
    total = 0
    reversed_num = number[::-1]
    for i, char in enumerate(reversed_num):
        digit = int(reversed_num[i])
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


is_admin = filters.create(check_admin, 'is_admin')

is_user = filters.create(check_user, 'is_user')

is_owner = filters.create(check_owner, 'is_owner')

is_word_answer = filters.create(check_word_answer, 'is_word_answer')

is_insult = filters.create(check_insult, 'is_insult')

is_spam = filters.create(check_spam, 'is_spam')

is_block = filters.create(check_block, 'is_block')

is_first_time = filters.create(check_first_time, 'is_first_time')


@app.on_message(
    filters.text & filters.command(
        ['addWord', 'delWord', 'listWords', 'addInsult', 'delInsult', 'listInsults', 'restart', 'ban', 'block',
         'unblock', 'addAdmin', 'delAdmin', 'listAdmins', 'allow', 'disallow'],
        list('/\\!#.')) & is_admin)
async def admin_message(client: Client, message: Message):
    if 'addword' == message.command[0].lower():
        if not len(message.command) >= 2 or not len(message.command[1].split('|')) == 2:
            await message.reply('**Enter the command in following format:\n`#addWord Keyword|Answer message**', True)
            return
        result = message.command[1].split('|')
        if len(message.command) > 2:
            result[1] += ' ' + (' '.join(message.command[2:]))
        try:
            await loop.run_in_executor(None,
                                       db.execute, f'INSERT INTO words (word, answer) values (?, ?)',
                                       result)
            await message.reply(f'**Keyword `{result[0]}` with answer `{result[1]}` has been added**', True)
        except sqlite3.IntegrityError:
            await message.reply(f'**Keyword `{result[0]}` already exists**')
        del result
    elif 'addinsult' == message.command[0].lower():
        if not len(message.command) >= 2:
            await message.reply('**Enter the command in following format:\n`#addInsult Keyword**', True)
            return
        text = '**Insult(s)** `'
        failed = '**Insult(s)** `'
        for i in message.text.split('\n')[1:]:
            try:
                await loop.run_in_executor(None,
                                           db.execute, f'INSERT INTO abuse_words (word) values (?)',
                                           [i])
                text += f'{i}, '
            except sqlite3.IntegrityError:
                failed += f'{i}, '
        text += '`**has been added**'
        failed += '`**already exists**'
        await message.reply(text, True)
        await message.reply(failed, True)
    elif 'delword' == message.command[0].lower():
        if not len(message.command) == 2:
            await message.reply('**Enter the command in following format:**\n`#delWord keyword`', True)
            return
        result = message.command[1]
        await loop.run_in_executor(None,
                                   db.execute, f'DELETE FROM words WHERE word = ?',
                                   [result])
        await message.reply(f'**Keyword `{result}` has been deleted**', True)
        del result
    elif 'delinsult' == message.command[0].lower():
        if not len(message.command) == 2:
            await message.reply('**Enter the command in following format:**\n`#delInsult keyword`', True)
            return
        result = message.command[1]
        await loop.run_in_executor(None,
                                   db.execute, f'DELETE FROM abuse_words WHERE word = ?',
                                   [result])
        await message.reply(f'**Keyword `{result}` has been deleted**', True)
        del result
    elif 'listwords' == message.command[0].lower():
        rows = await loop.run_in_executor(None,
                                          db.execute(f'SELECT word,answer,added FROM words').fetchall)
        if rows is not None and any(rows):
            text = '**Keywords List**\n\n'
            i = 1
            for word, answer, added in rows:
                text += f'`{i}`>> `{word}` -> `{answer}` :: `{added}`\n'
                i += 1
        else:
            text = '**Keywords List Is Empty**'
        await message.reply(text, True, 'Markdown')
        del rows
    elif 'listinsults' == message.command[0].lower():
        rows = await loop.run_in_executor(None,
                                          db.execute(f'SELECT word,added FROM abuse_words').fetchall)
        if rows is not None and any(rows):
            text = '**Insults List**\n\n'
            i = 1
            for word, added in rows:
                text += f'`{i}`>> `{word}` :: `{added}`\n'
                i += 1
        else:
            text = '**Keywords List Is Empty**'
        counter = 1
        last_text = ''
        for part in text.split('\n'):
            if counter < 33:
                last_text += f'{part}\n'
                counter += 1
                continue
            await message.reply(last_text, True, 'Markdown')
            last_text = ''
            counter = 1
        del text, last_text
        del rows
    elif 'restart' == message.command[0].lower():
        await message.reply('Restarting ...')
        await message.delete()
        os.execv(sys.executable, ['py3'] + sys.argv)
    elif 'ban' == message.command[0].lower():
        if len(message.command) > 1:
            user = (await client.get_users([message.command[1]]))[-1]

        elif hasattr(message, 'reply_to_message'):
            user = message.reply_to_message.from_user
        else:
            await message.reply(
                '**Reply this command on a message or use a user identifier after command:**\n#ban @username', True)
            return
        counter = 0
        async for dialog in client.iter_dialogs():
            try:
                if dialog.chat.type.lower() not in ['group', 'supergroup']:
                    continue
                await dialog.chat.restrict_member(user.id, ChatPermissions(can_send_messages=False))
                counter += 1
            except Exception as e:
                print(e)
        await message.reply(f'**User [{user.first_name}](tg://user?id={user.id}) got banned from `{counter}` groups**')
    elif 'block' == message.command[0].lower():
        if len(message.command) > 1:
            user = (await client.get_users([message.command[1]]))[-1]

        elif hasattr(message, 'reply_to_message'):
            user = message.reply_to_message.from_user
        else:
            await message.reply(
                '**Reply this command on a message or use a user identifier after command:**\n#block @username', True)
            return
        try:
            await user.block()
            await loop.run_in_executor(None, db.execute,
                                       'INSERT INTO users (userid, username, first_name, blocked) VALUES (?, ?, ?, ?) ON CONFLICT(userid) DO UPDATE SET blocked = TRUE',
                                       [user.id, user.username, user.first_name,
                                        True])
            await message.reply(f'**User [{user.first_name}](tg://user?id={user.id}) has been blocked**', True)
        except Exception as e:
            pass
    elif 'allow' == message.command[0].lower():
        if len(message.command) > 1:
            user = (await client.get_users([message.command[1]]))[-1]

        elif hasattr(message, 'reply_to_message'):
            user = message.reply_to_message.from_user
        else:
            await message.reply(
                '**Reply this command on a message or use a user identifier after command:**\n#allow @username', True)
            return
        try:
            await loop.run_in_executor(None, db.execute,
                                       'INSERT INTO users (userid, username, first_name, private) VALUES (?, ?, ?, TRUE) '
                                       'ON CONFLICT(userid) DO UPDATE SET private = TRUE',
                                       [user.id, user.username, user.first_name])
        except sqlite3.IntegrityError:
            pass
        await message.reply(f'**User [{user.first_name}](tg://user?id={user.id}) has been allowed to use this bot**', True)
    elif 'disallow' == message.command[0].lower():
        if len(message.command) > 1:
            user = (await client.get_users([message.command[1]]))[-1]
        elif hasattr(message, 'reply_to_message'):
            user = message.reply_to_message.from_user
        else:
            await message.reply(
                '**Reply this command on a message or use a user identifier after command:**\n#disAllow @username', True)
            return
        try:
            await loop.run_in_executor(None, db.execute,
                                       'INSERT INTO users (userid, username, first_name, private) VALUES (?, ?, ?, False) '
                                       'ON CONFLICT(userid) DO UPDATE SET private = False',
                                       [user.id, user.username, user.first_name])
        except sqlite3.IntegrityError:
            pass
        await message.reply(f'**User [{user.first_name}](tg://user?id={user.id}) has been disallowed to use this bot**', True)
    elif 'unblock' == message.command[0].lower():
        if len(message.command) > 1:
            user = (await client.get_users([message.command[1]]))[-1]

        elif hasattr(message, 'reply_to_message'):
            user = message.reply_to_message.from_user
        else:
            await message.reply(
                '**Reply this command on a message or use a user identifier after command:**\n#unblock @username', True)
            return
        try:
            await user.unblock()
            await loop.run_in_executor(None, db.execute,
                                       'INSERT INTO users (userid, username, first_name, blocked) VALUES (?, ?, ?, ?) ON CONFLICT(userid) DO UPDATE SET blocked = False',
                                       [user.id, user.username, user.first_name,
                                        False])
            await message.reply(f'**User [{user.first_name}](tg://user?id={user.id}) has been unblocked**', True)
        except Exception as e:
            await message.reply(f'Error: {e}', True)

    elif 'deladmin' == message.command[0].lower():
        if len(message.command) > 1:
            user = (await client.get_users([message.command[1]]))[-1]

        elif hasattr(message, 'reply_to_message'):
            user = message.reply_to_message.from_user
        else:
            await message.reply(
                '**Reply this command on a message or use a user identifier after command:**\n#addAdmin @username',
                True)
            return
        try:
            await loop.run_in_executor(None, db.execute, 'DELETE FROM admins WHERE userid = ?', [user.id])
            await message.reply(
                f'**User [{user.first_name}](tg://user?id={user.id}) has been deleted from admin list**', True)
        except Exception as e:
            await message.reply(f'Error: {e}', True)
    elif 'listadmins' == message.command[0].lower():
        rows = await loop.run_in_executor(None, db.execute('SELECT userid, first_name, added FROM admins').fetchall)
        if rows is None or not any(rows):
            text = '**Admin list is empty**'
        else:
            text = f'**Admin list:**\n\n'
            counter = 1
            for userid, first_name, added in rows:
                text += f'**`{counter}`) [{first_name}](tg://user?id={userid}) :: `{added}`**'
        await message.reply(text, True)
    elif 'addadmin' == message.command[0].lower():
        if len(message.command) > 1:
            user = (await client.get_users([message.command[1]]))[-1]

        elif hasattr(message, 'reply_to_message'):
            user = message.reply_to_message.from_user
        else:
            await message.reply(
                '**Reply this command on a message or use a user identifier after command:**\n#addAdmin @username',
                True)
            return
        try:
            await loop.run_in_executor(None, db.execute,
                                       'INSERT INTO admins (userid, username, first_name) VALUES (?, ?, ?)', [user.id,
                                                                                                              user.username,
                                                                                                              user.first_name])
            await message.reply(f'**User [{user.first_name}](tg://user?id={user.id}) has been added to admin list**',
                                True)
        except sqlite3.IntegrityError:
            await message.reply(f'**User [{user.first_name}](tg://user?id={user.id}) is already in admin list**', True)
        except Exception as e:
            await message.reply(f'Error: {e}', True)


@app.on_message(filters.text & filters.private & is_first_time)
async def first_time_message(client: Client, message: Message):
    # noinspection PyPep8Naming
    realSamy = (await client.get_users(['realSamy']))[0]
    text = f"""SinBot Protection Service Is Online

Ok My Master Got Your Message He will Answer You Shortly But till Then please don't Spam His Dm else SinBot Protection will block you 

🛡️TELETHON🛡️ : (will show current telethon virson)
🔥🔥Sin bot virson   : 7.5🔥🔥

⚠️🄲🄷🄰🄽🄽🄴🄻⚠️   : @sinchan_userbot
🔥CREATOR🔥    : @sinchan_offical

🔥Sin Bot օառɛʀ🔥   : @sinchan_offical

    📜⚡️License verified⚡️📜

➾ ᴍʏ ᴍᴀsᴛᴇʀ** ☞ (Here it will show who using this bot)"""
    # await message.reply_video('BAACAgUAAxkBAAIUC2ARLN0npKq83bFDfM_Ry13j__p9AAKnAQACcouIVHJTH3yLVscBHgQ', False, text)
    await client.copy_message(message.chat.id, '@skladjflkasjdflk', 360)


# noinspection SpellCheckingInspection


@app.on_message(filters.text & filters.bot)
async def bot_messages(client: Client, message: Message):
    if message.from_user.username.lower() == 'missrose_bot':
        info = await loop.run_in_executor(None, db.execute(
            'SELECT chat_id, message_id FROM rose_messages WHERE rose_message_id = ?',
            [message.reply_to_message.message_id]).fetchone)
        await message.copy(info[0], reply_to_message_id=info[1])
        await loop.run_in_executor(None, db.execute, 'DELETE FROM rose_messages WHERE rose_message_id = ?',
                                   [message.reply_to_message.message_id])


@app.on_message(is_block)
async def ignore_message(*args):
    pass


@app.on_message(is_spam)
async def insult_message(client: Client, message: Message):
    await message.from_user.block()
    await loop.run_in_executor(None, db.execute,
                               'INSERT INTO users (userid, username, first_name, blocked) VALUES (?, ?, ?, ?) ON CONFLICT(userid) DO UPDATE SET blocked = TRUE',
                               [message.from_user.id, message.from_user.username, message.from_user.first_name, True])


@app.on_message(filters.text & filters.group & is_word_answer)
async def answer_to_words(client, message: Message):
    answer = await loop.run_in_executor(None, db.execute('SELECT answer FROM words WHERE word = ?',
                                                         [message.text]).fetchone)
    await message.reply(' '.join(answer), True)
    await flood_handler(message)


@app.on_message(filters.text & filters.command(['yt', 'fedstat', 'ccgen', 'cccheck', 'help'],
                                               list('/\\!#.')))
async def all_message(client: Client, message: Message):
    await flood_handler(message)
    if message.command[0].lower() == 'yt' and len(message.command) > 1:
        audio = False
        url = message.command[1]
        if len(message.command) == 3 and message.command[1].lower() == 'mp3':
            audio = True
            url = message.command[2]
        audio_or_video = 'audio' if audio else 'video'
        # https://www.youtube.com/watch?v=E91vM9_3_T4
        if re.match('^(https?://)?(www[.])?youtube[.]com/watch[?]v=[a-z0-9_.-]+$', url, re.I) is None:
            await message.reply(
                '**Invalid url, try another url in following format:\nhttps://www.youtube.com/watch?v=mx6MzHYzEfY**')
        else:
            sent = await message.reply(f'**Preparing to send {audio_or_video}...**')
            try:
                yt = YouTube(url)
                stream = yt.streams.filter(only_audio=audio, progressive=not audio, subtype='mp4').first()
                last_time = MyValues(round(time()))
                r = await loop.run_in_executor(None, get, yt.thumbnail_url)
                thumb_path = f'./{r.url.split("/")[-1]}'
                with open(thumb_path, 'wb') as f:
                    f.write(r.content)
                # key = 'abb6eeac09f4b3cda002e5cd91154ed41de4f'
                url = str(stream.url)
                # result = await loop.run_in_executor(None, get, f'http://cutt.ly/api/api.php?key={key}&short={url}')
                # url = dict(result.json()).get('url').get('shortLink')
                await message.reply_video(url, True, f'**{yt.title}**\n\n{yt.description[0:900]}...',
                                          progress=progress_handler,
                                          progress_args=(
                                              sent, round(time()),
                                              last_time), duration=yt.length,
                                          thumb=thumb_path) if not audio else await message.reply_audio(
                    url, True, f'**{yt.title}**\n\n{yt.description[0:900]}...',
                    progress=progress_handler, progress_args=(
                        sent, round(time()),
                        last_time), duration=yt.length, thumb=thumb_path)
                return
            except WebpageCurlFailed:
                path = await loop.run_in_executor(None, stream.download)
                try:
                    await message.reply_video(path, True, f'**{yt.title}**\n\n{yt.description[0:900]}...',
                                              progress=progress_handler,
                                              progress_args=(
                                                  sent, round(time()),
                                                  last_time), duration=yt.length,
                                              thumb=thumb_path) if not audio else await message.reply_document(
                        path, True, thumb_path, f'**{yt.title}**\n\n{yt.description[0:900]}...',
                        progress=progress_handler, progress_args=(
                            sent, round(time()),
                            last_time))
                except Exception as e:
                    await message.reply(f'Error: {e}')
                    del e
                os.remove(path)
                os.remove(thumb_path)
                await sent.delete()
                return
            except Exception as e:
                await message.reply(f'Error: {e}')
                del e
            await message.reply(f'**Failed to download {audio_or_video}**', True)
    elif message.command[0].lower() == 'ytlinks' and len(message.command) > 1:
        audio = False
        url = message.command[1]
        if len(message.command) == 3 and message.command[1].lower() == 'mp3':
            audio = True
            url = message.command[2]

        # https://www.youtube.com/watch?v=E91vM9_3_T4
        pattern = '^(https?://)?(www[.])?youtube[.]com/watch[?]v=[a-z0-9-_]+$'
        if re.match(pattern, url, re.I) is None:
            await message.reply(
                '**Invalid url, try another url in following format:\nhttps://www.youtube.com/watch?v=mx6MzHYzEfY**',
                True, disable_web_page_preview=True)
        else:
            yt = YouTube(url)
            text = f'**Download Links Of [{url}]\n\n'
            sent = await message.reply(text, True)
            for stream in yt.streams.all():
                text = f'**FPS: `{stream.fps}`, Codecs: `{str(stream.codecs)}`, Bitrate: `{stream.bitrate}`,' \
                       f' Url: \n[Click Here]({str(stream.url)})**'
                await sent.reply(text, True)
            await message.reply('**Done!**', True)
    elif 'fedstat' == message.command[0].lower():
        if len(message.command) == 2:
            user = (await client.get_users([message.command[1]]))[-1]
        else:
            user = message.from_user
        sent = await client.send_message('@MissRose_bot', f'/fedstat {user.id}')
        await loop.run_in_executor(None, db.execute,
                                   'INSERT INTO rose_messages (chat_id, message_id, rose_message_id) VALUES (?, ?, ?)',
                                   [message.chat.id, message.message_id, sent.message_id])
    elif 'fbanstat' == message.command[0].lower() and len(message.command) == 2:
        ban_id = message.command[1]
        sent = await client.send_message('@MissRose_bot', f'/fbanstat {ban_id}')
        await loop.run_in_executor(None, db.execute,
                                   'INSERT INTO rose_messages (chat_id, message_id, rose_message_id) VALUES (?, ?, ?)',
                                   [message.chat.id, message.message_id, sent.message_id])
    elif 'ccgen' == message.command[0].lower():
        length = 1
        if len(message.command) == 2:
            length = max(length, int(message.command[1]))
        text = ''
        while True:
            card_info = cc_gen()
            card_num = card_info[0]
            check = cc_check(card_num)
            if check:
                text += f'`{card_num}`|`{card_info[1]}`|`{card_info[2]}`|`{card_info[3]}`\n'
                length -= 1
                if length <= 0:
                    break
        await message.reply(text, True)
    elif 'cccheck' == message.command[0].lower() and len(message.command) >= 2:
        card_num = ''.join(message.command[1:]).split('|')[0]
        check = cc_check(card_num)
        await message.reply('**Valid**' if check else '**Not Valid**', True)
    elif 'help' == message.command[0].lower():
        text = '''**ADMINS' COMMANDS

#addAdmin [`User` or `Reply`]
#delAdmin [`User` or `Reply`]
#listAdmins

#addWord `Word`|`Answer`
#delWord `Word`
#listWords

#addInsult `Insult` __(you can use multiple insult statements in separated lines)__
#delInsult `Insult`
#listInsults

#ban [`User` or `Reply`]
#block [`User` or `Reply`]
#unblock [`User` or `Reply`]
#allow [`User` or `Reply`]
#disallow [`User` or `Reply`]

USERS' COMMANDS

#YT `Video Link`
#YT mp3 `Video Link` __(Will send video sound)__
#FetState [`User` or `Reply`]
#CCGen `Length` __(Defaults to 1)__
#CCCheck `Card Number`**'''
        await message.reply(text, True)


@app.on_message(filters.private & is_user)
async def flood_get(client: Client, message: Message):
    await flood_handler(message)
    return


print('Initializing Pyrogram, A Moment Please...')
app.run()
