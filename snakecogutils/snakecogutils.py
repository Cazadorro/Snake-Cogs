import discord
from datetime import datetime
from discord.ext import commands
from cogs.utils.dataIO import dataIO
from random import choice
from collections import namedtuple, OrderedDict
from copy import deepcopy
from __main__ import send_cmd_help
from .utils import checks
import logging
import os


description = "What're ya buyin', PEN ISLAND traveler?"


class TestBot:
    def __init__(self, bot):
        self.bot = bot
        self.description = "Wasdf"

    @commands.group(name="testicular", pass_context=True)
    async def _testicular(self, ctx):
        """Inventory operations."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @_testicular.command(pass_context=True, no_pm=True)
    async def one(self, ctx):
        """Registers an inventory with the Armorsmith."""
        author = ctx.message.author
        await self.bot.say("test message")



def setup(bot):
    n = TestBot(bot)
    bot.add_cog(n)
