import discord
import sys
import random
import asyncio
import time
import datetime
import re

from discord.ext import commands
from discord.ext.commands import errors, Cog
from utils import create_tables, sqlite, default

# Test DB before launching
tables = create_tables.creation(debug=True)
if not tables:
    sys.exit(1)

# Local variables for index.py
config = default.get("config.json")
bot = commands.Bot(
    command_prefix=config.prefix, prefix=config.prefix, command_attrs=dict(hidden=True),
    intents=discord.Intents(guilds=True, messages=True)
)


class BirthdayBot(Cog):
    def __init__(self, bot):
        self.bot = bot
        self.re_timestamp = r"^(0[0-9]|1[0-9]|2[0-9]|3[0-1])\/(0[1-9]|1[0-2])\/([1-2]{1}[0-9]{3})"
        self.db = sqlite.Database()
        print("Logging in...")

    @commands.Cog.listener()
    async def on_command_error(self, ctx, err):
        if isinstance(err, errors.MissingRequiredArgument) or isinstance(err, errors.BadArgument):
            helper = str(ctx.invoked_subcommand) if ctx.invoked_subcommand else str(ctx.command)
            await ctx.send_help(helper)

        elif isinstance(err, errors.CommandInvokeError):
            error = default.traceback_maker(err.original)
            await ctx.send(f"Fehler beim Laden yk ;-;\n{error}")

        elif isinstance(err, errors.MaxConcurrencyReached):
            await ctx.send("Du benutz zu viele Commands auf einmal, immer ruhig bleiben....")

        elif isinstance(err, errors.CheckFailure):
            pass

        elif isinstance(err, errors.CommandOnCooldown):
            await ctx.send(f"Versuch es in {err.retry_after:.2f} sekunden noch einmal.")

        elif isinstance(err, errors.CommandNotFound):
            pass

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'Ready: {self.bot.user} | Servers: {len(self.bot.guilds)}')
        await self.bot.change_presence(
            activity=discord.Activity(type=3, name="wann hast du Geburtstag? 🎉🎂 (Prefix: G)"),
            status=discord.Status.idle
        )

        while True:
            await asyncio.sleep(10)
            guild = self.bot.get_guild(config.guild_id)
            birthday_role = discord.Object(id=config.birthday_role_id)

            # Check if someone has birthday today
            birthday_today = self.db.fetch(
                "SELECT * FROM birthdays WHERE has_role=0 AND strftime('%m-%d', birthday) = strftime('%m-%d', 'now')"
            )
            if birthday_today:
                for g in birthday_today:
                    self.db.execute("UPDATE birthdays SET has_role=1 WHERE user_id=?", (g["user_id"],))
                    try:
                        user = guild.get_member(g["user_id"])
                        await user.add_roles(birthday_role, reason=f"{user} Hat Geburtstag 🎂🎉")
                        await self.bot.get_channel(config.announce_channel_id).send(
                            f"Happy birthday {user.mention}, habe einen schönen Geburtstag! 🎂🎉"
                        )
                        print(f"Gave role to {user.name}")
                    except Exception:
                        pass  # meh, just skip it...

            birthday_over = self.db.fetch(
                "SELECT * FROM birthdays WHERE has_role=1 AND strftime('%m-%d', birthday) != strftime('%m-%d', 'now')"
            )
            for g in birthday_over:
                self.db.execute("UPDATE birthdays SET has_role=0 WHERE user_id=?", (g["user_id"],))
                try:
                    user = guild.get_member(g["user_id"])
                    await user.remove_roles(birthday_role, reason=f"{user} hat heute nicht Geburtstag...")
                    print(f"Removed role from {user.name}")
                except Exception:
                    pass  # meh, just skip it...

    def check_birthday_noted(self, user_id):
        """ Convert timestamp string to datetime """
        data = self.db.fetchrow("SELECT * FROM birthdays WHERE user_id=?", (user_id,))
        if data:
            return data["birthday"]
        else:
            return None

    def calculate_age(self, born):
        """ Calculate age (datetime) """
        today = datetime.datetime.utcnow()
        age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        return age

    def ifelse(self, statement, if_statement: str, else_statement: str = None):
        """ Make it easier with if/else cases of what grammar to use
        - if_statement is returned when statement is True
        - else_statement is returned when statement is False/None
        """
        else_statement = else_statement if else_statement else ""
        return if_statement if statement else else_statement

    @commands.command()
    async def ping(self, ctx):
        """ Pong! """
        before = time.monotonic()
        before_ws = int(round(self.bot.latency * 1000, 1))
        message = await ctx.send("Loading...")
        ping = int((time.monotonic() - before) * 1000)
        await message.edit(content=f"🏓 WS: {before_ws}ms  |  REST: {ping}ms")

    @commands.command()
    async def time(self, ctx):
        """ Check what the time is for me (the bot) """
        time = datetime.datetime.utcnow().strftime("%d %B %Y, %H:%M")
        await ctx.send(f"Currently the time for me is **{time}**")

    @commands.command()
    async def source(self, ctx):
        """ Schau gerne auf meinem GitHub vorbei <3 """
        # Do not remove this command, this has to stay due to the GitHub LICENSE.
        # 
        # Reference: 
        await ctx.send(f"**{ctx.bot.user}** den Bot findest du in dieser Repo:\nhttps://github.com/real-airbauer/chilllounge-geburtstage")

    @commands.command(aliases=['b', 'bd', 'birth', 'day'])
    async def birthday(self, ctx, *, user: discord.Member = None):
        """ Check your birthday or other people """
        user = user or ctx.author

        if user.id == self.bot.user.id:
            return await ctx.send("Ich habe am **24 November** Geburtstag, danke das du Fragst ❤")

        has_birthday = self.check_birthday_noted(user.id)
        if not has_birthday:
            return await ctx.send(f"**{user.name}** hat mir seinen Geburtstag noch nicht verraten. :(")

        birthday = has_birthday.strftime('%d %B')
        age = self.calculate_age(has_birthday)

        is_author = user == ctx.author
        target = self.ifelse(is_author, "**You** have", f"**{user.name}** has")
        grammar = self.ifelse(is_author, "you're", "is")
        when = self.ifelse(is_author, " ", " on ")

        await ctx.send(
            f"{target} Geburtstag ist am{when}**{birthday}** und er/sie {grammar} ist gerade **{age}** Jahre alt."
        )

    @commands.command()
    @commands.max_concurrency(1, per=commands.BucketType.user)
    async def set(self, ctx):
        """ Set your birthday :) """
        has_birthday = self.check_birthday_noted(ctx.author.id)
        if has_birthday:
            return await ctx.send(
                f"Du hast mir schon gesagt das du am **{has_birthday.strftime('%d %B %Y')}**\n Geburtstag hast."
                f"Um deinen Geburtstag zu ändern wende dich an Kathi oder Vik....besser..Vik..."
            )

        start_msg = await ctx.send(f"Na du **{ctx.author.name}**, sag mir bitte wann du Gebren bist. `[ TAG/MONAT/JAHR ]`")
        confirmcode = random.randint(10000, 99999)

        def check_timestamp(m):
            if (m.author == ctx.author and m.channel == ctx.channel):
                if re.compile(self.re_timestamp).search(m.content):
                    return True
            return False

        def check_confirm(m):
            if (m.author == ctx.author and m.channel == ctx.channel):
                if (m.content.startswith(str(confirmcode))):
                    return True
            return False

        try:
            user = await self.bot.wait_for('message', timeout=30.0, check=check_timestamp)
        except asyncio.TimeoutError:
            return await start_msg.edit(
                content=f"~~{start_msg.clean_content}~~\n\nfine then, I won't save your birthday :("
            )

        timestamp = datetime.datetime.strptime(user.content.split(" ")[0], "%d/%m/%Y")
        timestamp_clean = timestamp.strftime("%d %B %Y")
        today = datetime.datetime.now()
        age = self.calculate_age(timestamp)

        if timestamp > today:
            return await ctx.send(f"Nein...du kannst nicht aus der Zukunft kommen. **{ctx.author.name}**")
        if age > 122:
            return await ctx.send(f"Der Älteste Mensch wurde **122**, ich glaub nicht das du Älter bist **{ctx.author.name}**...")
        if age <= 12:
            return await ctx.send(f"Du Solltest mindistens **13** sein um Discord benutzen zu dürfen **{ctx.author.name}**, bist du eta zu Jung? 🤔")

        confirm_msg = await ctx.send(
            f"Alright **{ctx.author.name}**, du bestätigst das dein Geburtstag am **{timestamp_clean}** ist"
            f"und du gerade **{age}** Jahre alt bist?\nType `{confirmcode}` um das zu bestätigen\n"
            f"(Du Kannst das später nicht mehr ändern!)"
        )

        try:
            user = await self.bot.wait_for('message', timeout=30.0, check=check_confirm)
        except asyncio.TimeoutError:
            return await confirm_msg.edit(
                content=f"~~{confirm_msg.clean_content}~~\n\nStopped process..."
            )

        self.db.execute("Dein Geburtstag wird geladen (?, ?, ?)", (ctx.author.id, timestamp, False))
        await ctx.send(f"Fertig, deinen Geburtstag habe ich mir am **{timestamp_clean}** notiert!🎂")

    @commands.command()
    @commands.check(default.is_owner)
    async def forceset(self, ctx, user: discord.Member, *, time: str):
        timestamp = datetime.datetime.strptime(time, "%d/%m/%Y")
        data = self.db.execute("UPDATE birthdays SET birthday=? WHERE user_id=?", (timestamp, user.id))
        await ctx.send(data)

    @commands.command()
    @commands.check(default.is_owner)
    async def db(self, ctx, *, query: str):
        data = self.db.execute(query)
        await ctx.send(f"{data}")

    @commands.command()
    @commands.check(default.is_owner)
    async def dropall(self, ctx):
        data = self.db.execute("DELETE FROM birthdays")
        await ctx.send(f"DEBUG: {data}")

    @commands.command()
    @commands.check(default.is_owner)
    async def dropuser(self, ctx, *, user: discord.Member):
        data = self.db.execute("DELETE FROM birthdays WHERE user_id=?", (user.id,))
        await ctx.send(f"DEBUG: {data}")


bot.add_cog(BirthdayBot(bot))
bot.run(config.token)

# <3