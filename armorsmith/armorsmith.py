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



class ArmorException(Exception):
    pass


class InventoryException(Exception):
    pass


class AccountAlreadyExists(InventoryException):
    pass


class NoAccount(InventoryException):
    pass


class ItemNotFound(InventoryException):
    pass


class SameSenderAndReceiver(InventoryException):
    pass


class Item(namedtuple('Item', 'name cost')):
    @staticmethod
    def _roll_dice(dice):
        """Returns the value of rolling XdY dice
        Ex: _roll_dice("2d6") returns the result of rolling 2 six-sided die"""
        (num_rolls, dice_sides) = map(int, dice.split('d'))
        val = 0
        for roll in range(num_rolls):
            val += choice(range(1, dice_sides + 1))
        return val

    def __str__(self):
        s = ""
        for name, value in self._asdict().items():
            s += "{}: {}\n".format(name, value)
        s += ""
        return s

    def __repr__(self):
        return self.name


class Weapon(namedtuple('Weapon', Item._fields + ('hit_dice',)), Item):
    def _damage_roll(self):
        return self._roll_dice(self.hit_dice)


class Armor(namedtuple('Armor', Item._fields + ('damage_reduction',)), Item):
    def _block_damage(self, damage):
        return damage - self.damage_reduction


class HealPotion(namedtuple('HealPotion', Item._fields + ('heal_dice',)), Item):
    def _healing_roll(self):
        return self._roll_dice(self.heal_dice)


class Inventory:
    def __init__(self, bot, file_path):
        self.bot = bot
        self.accounts = dataIO.load_json(file_path)

    def create_account(self, user):
        server = user.server
        if not self.account_exists(user):
            if server.id not in self.accounts:
                self.accounts[server.id] = {}
            if user.id in self.accounts:  # Legacy account
                stash = self.accounts[user.id]["stash"]
            else:
                stash = OrderedDict()
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            account = {"name": user.name,
                       "stash": stash,
                       "created_at": timestamp
                       }
            self.accounts[server.id][user.id] = account
            self._save_inventory()
            return self.get_account(user)
        else:
            raise AccountAlreadyExists()

    def account_exists(self, user):
        try:
            self._get_account(user)
        except NoAccount:
            return False
        return True

    def has_item(self, user, item):
        account = self._get_account(user)
        stash = account["stash"]
        if item.name in stash.keys():
            return True
        else:
            return False

    def remove_item(self, user, item):
        server = user.server
        account = self._get_account(user)
        stash = account["stash"]
        if self.has_item(user, item):
            del stash[item.name]
            self.accounts[server.id][user.id] = account
            self._save_inventory()
        else:
            raise ItemNotFound()

    def give_item(self, user, item):
        server = user.server
        account = self._get_account(user)
        stash = account["stash"]
        stash[item.name] = item
        self.accounts[server.id][user.id] = account
        self._save_inventory()

    def transfer_item(self, sender, receiver, item):
        if sender is receiver:
            raise SameSenderAndReceiver()
        if self.account_exists(sender) and self.account_exists(receiver):
            if not self.has_item(sender, item):
                raise ItemNotFound()
            self.remove_item(sender, item)
            self.give_item(receiver, item)
        else:
            raise NoAccount()

    def wipe_inventories(self, server):
        self.accounts[server.id] = {}
        self._save_inventory()

    def get_server_accounts(self, server):
        if server.id in self.accounts:
            raw_server_accounts = deepcopy(self.accounts[server.id])
            accounts = []
            for k, v in raw_server_accounts.items():
                v["id"] = k
                v["server"] = server
                acc = self._create_account_obj(v)
                accounts.append(acc)
            return accounts
        else:
            return []

    def get_all_accounts(self):
        accounts = []
        for server_id, v in self.accounts.items():
            server = self.bot.get_server(server_id)
            if server is None:
                # Servers that have since been left will be ignored
                # Same for users_id from the old bank format
                continue
            raw_server_accounts = deepcopy(self.accounts[server.id])
            for k, v in raw_server_accounts.items():
                v["id"] = k
                v["server"] = server
                acc = self._create_account_obj(v)
                accounts.append(acc)
        return accounts

    def get_stash(self, user):
        account = self._get_account(user)
        return [str(x) for x in account["stash"]]

    def get_account(self, user):
        acc = self._get_account(user)
        acc["id"] = user.id
        acc["server"] = user.server
        return self._create_account_obj(acc)

    def _create_account_obj(self, account):
        account["member"] = account["server"].get_member(account["id"])
        account["created_at"] = datetime.strptime(account["created_at"],
                                                  "%Y-%m-%d %H:%M:%S")
        Account = namedtuple("Account", "id name stash "
                                        "created_at server member")
        return Account(**account)

    def _save_inventory(self):
        dataIO.save_json("data/armorsmith/inventory.json", self.accounts)

    def _get_account(self, user):
        server = user.server
        try:
            return deepcopy(self.accounts[server.id][user.id])
        except KeyError:
            raise NoAccount()


class Store:
    """Interface to item list"""

    def __init__(self, bot, file_path):
        self.bot = bot
        self.file_path = file_path
        self.inventory = {"weapons": [],
                          "armor": [],
                          "potions": []}
        self._generate_inventory()
        self.dependencies = ["snakecogutils"]

    def _generate_inventory(self):
        item_list = dataIO.load_json(self.file_path)
        for weapon in item_list["weapons_list"]:
            self.inventory["weapons"].append(Weapon(
                weapon["name"],
                weapon["cost"],
                weapon["hit_dice"]
            ))
        for armor in item_list["armor_list"]:
            self.inventory["armor"].append(Armor(
                armor["name"],
                armor["cost"],
                armor["damage_reduction"]
            ))
        for potion in item_list["potion_list"]:
            self.inventory["potions"].append(HealPotion(
                potion["name"],
                potion["cost"],
                potion["heal_dice"]
            ))

    def list_items(self):
        self.bot.say(str(self.bot.cogs))
        for cogname in self.dependencies:
            self.bot.get_cog("Owner")._load_cog("cogs."+cogname)
        description = "What're ya buyin', PEN ISLAND traveler?" + self.bot.get_cog("TestBot").description
        embed = discord.Embed(colour=0xFF0000, description=description)
        embed.title = "Item Shop"
        embed.set_author(name="Shopkeep", icon_url="http://imgur.com/zFYAFVg.jpg")
        embed.add_field(name="Weapons", value='\n'.join([str(x) for x in self.inventory["weapons"]]))
        embed.add_field(name="Armor", value='\n'.join([str(x) for x in self.inventory["armor"]]))
        embed.add_field(name="Potions", value='\n'.join([str(x) for x in self.inventory["potions"]]))
        embed.set_footer(text="Buy using [p]store buy <item name>")
        return embed

    def get_item_by_name(self, item_name):
        for item_type in self.inventory.values():
            for item in item_type:
                if item.name == item_name:
                    return item
        raise ItemNotFound


class Armorsmith:
    def __init__(self, bot):
        self.bot = bot
        self.inventory = Inventory(bot, "data/armorsmith/inventory.json")
        self.store = Store(bot, "data/armorsmith/items.json")
        self.bank = self.bot.get_cog("Economy").bank
        self.file_path = "data/armorsmith/settings.json"
        self.settings = dataIO.load_json(self.file_path)

    @commands.group(name="inventory", pass_context=True)
    async def _inventory(self, ctx):
        """Inventory operations."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @_inventory.command(pass_context=True, no_pm=True)
    async def register(self, ctx):
        """Registers an inventory with the Armorsmith."""
        author = ctx.message.author
        try:
            account = self.inventory.create_account(author)
            await self.bot.say("{} Stash opened.".format(author.mention))
        except AccountAlreadyExists:
            await self.bot.say("{} You already have a stash with the Armorsmith".format(author.mention))

    @_inventory.command(pass_context=True)
    async def stash(self, ctx, user: discord.Member = None):
        """Shows stash of user,
        
        Defaults to yours."""
        if not user:
            user = ctx.message.author
            try:
                await self.bot.say("{} Your stash contains: {}".format(user.mention, self.inventory.get_stash(user)))
            except NoAccount:
                await self.bot.say(
                    "{} You don't have a stash with the Armorsmith. Type `{}inventory register` to open one".format(
                        user.mention, ctx.prefix))
        else:
            try:
                await self.bot.say("{}'s stash is {}".format(user.name, self.inventory.get_stash(user)))
            except NoAccount:
                await self.bot.say("That user has no inventory stash")

    @_inventory.command(pass_context=True)
    async def transfer(self, ctx, user: discord.Member, item: Item):
        """Transfers an item to other users."""
        author = ctx.message.author
        try:
            self.inventory.transfer_item(author, user, item)
            logger.info(
                "{} ({}) transferred {} to {}({})".format(author.name, author.id, item.name, user.name, user.id))
            await self.bot.say("{} has been transferred to {}'s stash.".format(item.name, user.name))
        except SameSenderAndReceiver:
            await self.bot.say("You can't transfer to yourself.")
        except ItemNotFound:
            await self.bot.say("Item was not found in your stash.")
        except NoAccount:
            await self.bot.say("That user has no stash account.")

    @_inventory.command(name="give", pass_context=True)
    @checks.admin_or_permissions(manage_server=True)
    async def _give(self, ctx, user: discord.Member, *, item_name: str):
        """Gives an item to a user."""
        author = ctx.message.author
        try:
            item_obj = self.store.get_item_by_name(item_name)
            self.inventory.give_item(user, item_obj)
            logger.info("{}({}) gave {} to {}({})".format(author.name, author.id, item_obj.name, user.name, user.id))
            await self.bot.say("{} has been given to {}".format(item_obj.name, user.name))
        except ItemNotFound:
            await self.bot.say("Item name does not exist")

    @_inventory.command(pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions(administrator=True)
    async def reset(self, ctx, confirmation: bool = False):
        """Deletes all server's stash accounts"""
        if confirmation is False:
            await self.bot.say(
                "This will delete all stash accounts on this server.\nIf you're sure, type {}inventory reset yes".format(
                    ctx.prefix))
        else:
            self.inventory.wipe_inventories(ctx.message.server)
            await self.bot.say("All stash accounts on this server have been deleted.")

    @commands.group(name="store", pass_context=True)
    async def _store(self, ctx):
        """Store operations."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @_store.command(pass_context=True, no_pm=False)
    async def list(self, ctx):
        """Lists all available items for purchase"""
        embed = self.store.list_items()
        await self.bot.whisper(embed=embed)

    @_store.command(pass_context=True, no_pm=True)
    async def buy(self, ctx, *, item_name):
        """Buy an item for yourself"""
        author = ctx.message.author
        try:
            item = self.store.get_item_by_name(item_name)
            self.bank.withdraw_credits(author, item.cost)
            self.inventory.give_item(author, item)
        except NoAccount:
            await self.bot.say("You do not have a stash register. Please do so before buying.")
        except ItemNotFound:
            await self.bot.say("The item specified does not exist.")

    # TODO: Add battles, battle-leaderboards, betting

    @commands.group(name="fight", pass_context=True)
    async def _fight(self, ctx):
        """Dueling operations."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @_fight.command(pass_contex=True, no_pm=True)
    async def duel(self, ctx, user: discord.User):
        author = ctx.message.author
        hp_author = 100
        hp_user = 100

    def already_in_list(self, accounts, user):
        for acc in accounts:
            if user.id == acc.id:
                return True
        return False

    @commands.group(pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_server=True)
    async def armorsmithset(self, ctx):
        """Changes Armorsmith module settings"""
        server = ctx.message.server
        settings = self.settings[server.id]
        if ctx.invoked_subcommand is None:
            msg = "```"
            for k, v in settings.items():
                msg += "{}: {}\n".format(k, v)
            msg += "```"
            await send_cmd_help(ctx)
            await self.bot.say(msg)

    def display_time(self, seconds, granularity=2):
        intervals = (  # Source: http://stackoverflow.com/a/24542445
            ('weeks', 604800),  # 60 * 60 * 24 * 7
            ('days', 86400),  # 60 * 60 * 24
            ('hours', 3600),  # 60 * 60
            ('minutes', 60),
            ('seconds', 1),
        )

        result = []

        for name, count in intervals:
            value = seconds // count
            if value:
                seconds -= value * count
                if value == 1:
                    name = name.rstrip('s')
                result.append("{} {}".format(value, name))
        return ', '.join(result[:granularity])


def check_folders():
    if not os.path.exists("data/armorsmith"):
        print("Creating data/armorsmith folder...")
        os.makedirs("data/armorsmith")


def check_files():
    f = "data/armorsmith/settings.json"
    if not dataIO.is_valid_json(f):
        print("Creating default armorsmith settings.json...")
        dataIO.save_json(f, {})

    f = "data/armorsmith/inventory.json"
    if not dataIO.is_valid_json(f):
        print("Creating empty inventory.json...")
        dataIO.save_json(f, {})

    f = "data/armorsmith/items.json"
    if not dataIO.is_valid_json(f):
        print("Item file not found/invalid. Creating blank item file")
        dataIO.save_json(f, {})


def setup(bot):
    global logger
    check_folders()
    check_files()
    logger = logging.getLogger("red.armorsmith")
    if logger.level == 0:
        # Prevents the logger from being loaded again in case of module reload
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler(filename='data/armorsmith/inventory.log', encoding='utf-8', mode='a')
        handler.setFormatter(logging.Formatter('%(asctime)s %(message)s', datefmt="[%d/%m/%Y %H:%M]"))
        logger.addHandler(handler)
    bot.add_cog(Armorsmith(bot))
