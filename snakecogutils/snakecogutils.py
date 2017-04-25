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
import asyncio

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

    @commands.command(pass_context=True, no_pm=True, name='get_in_here')
    async def get_in_here(self, ctx: commands.Context):
        author = ctx.message.author
        server = ctx.message.server
        voice_channel = author.voice_channel
        if self.bot.get_channel(server.id) is None or self.bot.get_channel(
                server.id) is not voice_channel:
            try:
                await self.bot.say("hello")
                voice_client = await self.bot.join_voice_channel(voice_channel)
                await self.bot.say(str(voice_client.socket))
                await self.bot.say("hello2")
                x = None
                index = 0
                while index < 100:
                    await self.bot.say("Index : " + str(index))
                    index += 1
                    try:
                        x = voice_client.socket.recvfrom(128)
                        await self.bot.say([x[0][i] for i in range(len(x[0]))])
                    except Exception:
                        pass
                    await self.bot.say(str(x[1]) + str(len(x[0])) if x is not None else "None")

                # await asyncio.wait_for(
                #     self.bot.join_voice_channel(voice_channel), timeout=5,
                #     loop=self.bot.loop)
            except asyncio.futures.TimeoutError as e:
                raise ConnectionError(
                    "Error connecting to voice channel; " + e)



def setup(bot):
    n = TestBot(bot)
    bot.add_cog(n)
