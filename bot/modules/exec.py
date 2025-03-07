from pyrogram.handlers import MessageHandler
from pyrogram.filters import command
from os import path as ospath, getcwd, chdir
from traceback import format_exc
from textwrap import indent
from io import StringIO, BytesIO
from contextlib import redirect_stdout
from aiofiles import open as aiopen

from bot import LOGGER, bot
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.message_utils import sendFile, sendMessage
from bot.helper.ext_utils.bot_utils import sync_to_async, new_task

namespaces = {}


def namespace_of(message):
    if message.chat.id not in namespaces:
        namespaces[message.chat.id] = {
            "__builtins__": globals()["__builtins__"],
            "bot": bot,
            "message": message,
            "user": message.from_user or message.sender_chat,
            "chat": message.chat,
        }

    return namespaces[message.chat.id]


def log_input(message):
    LOGGER.info(
        f"IN: {message.text} (user={message.from_user.id if message.from_user else message.sender_chat.id}, chat={message.chat.id})"
    )


async def send(msg, message):
    if len(str(msg)) > 2000:
        with BytesIO(str.encode(msg)) as out_file:
            out_file.name = "output.txt"
            await sendFile(message, out_file)
    else:
        LOGGER.info(f"OUT: '{msg}'")
        await sendMessage(message, f"<code>{msg}</code>")


@new_task
async def aioexecute(_, message):
    await send(await do("aexec", message), message)


@new_task
async def execute(_, message):
    await send(await do("exec", message), message)


def cleanup_code(code):
    if code.startswith("```") and code.endswith("```"):
        return "\n".join(code.split("\n")[1:-1])
    return code.strip("` \n")


async def do(func, message):
    log_input(message)
    content = message.text.split(maxsplit=1)[-1]
    body = cleanup_code(content)
    env = namespace_of(message)

    chdir(getcwd())
    async with aiopen(ospath.join(getcwd(), "bot/modules/temp.txt"), "w") as temp:
        await temp.write(body)

    stdout = StringIO()

    try:
        if func == "exec":
            exec(f"def func():\n{indent(body, '  ')}", env)
        else:
            exec(f"async def func():\n{indent(body, '  ')}", env)
    except Exception as e:
        return f"{e.__class__.__name__}: {e}"

    rfunc = env["func"]

    try:
        with redirect_stdout(stdout):
            if func == "exec":
                func_return = await sync_to_async(rfunc)
            else:
                func_return = await rfunc()
    except Exception as e:
        value = stdout.getvalue()
        return f"{value}{format_exc()}"
    else:
        value = stdout.getvalue()
        result = None
        if func_return is None:
            if value:
                result = f"{value}"
            else:
                try:
                    result = f"{repr(await sync_to_async(eval, body, env))}"
                except:
                    pass
        else:
            result = f"{value}{func_return}"
        if result:
            return result


async def clear(_, message):
    log_input(message)
    global namespaces
    if message.chat.id in namespaces:
        del namespaces[message.chat.id]
    await send("Locals Cleared.", message)


bot.add_handler(
    MessageHandler(
        aioexecute, filters=command(BotCommands.AExecCommand) & CustomFilters.owner
    )
)
bot.add_handler(
    MessageHandler(
        execute, filters=command(BotCommands.ExecCommand) & CustomFilters.owner
    )
)
bot.add_handler(
    MessageHandler(
        clear, filters=command(BotCommands.ClearLocalsCommand) & CustomFilters.owner
    )
)
