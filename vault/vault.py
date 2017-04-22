import discord
from discord.ext import commands
from cogs.utils.dataIO import dataIO
from collections import namedtuple, defaultdict, deque
from datetime import datetime
from copy import deepcopy
from .utils import checks
from cogs.utils.chat_formatting import pagify, box
from enum import Enum
from __main__ import send_cmd_help
import os
import time
import logging
import random
import asyncio


class InvalidTransactionException(Exception):
    def __init__(self, user_item_dict):
        exception_string = "Invalid transaction with: "
        for key, value in user_item_dict:
            exception_string += "{{{}:{}}}".format(key, value)
        super().__init__(self, exception_string)


class VaultClass:
    def __init__(self, bot, vault_path):
        """
        Initializes a "locker" of sorts which stores arbitrary items
        :param bot: discord bot object
        :param accounts_file_path: file path to accounts json
        """
        self.vault_path = vault_path
        self.accounts = dataIO.load_json(self.vault_path)
        self.bot = bot

    def create_account(self, user, *, account_name="", metadata={}, storage={}):
        """
        given a discord user, account name, metadata for account and initial 
        account storage will create an account or error on account already 
        existing
        :param user: discord user
        :param account_name: name of account to create for user
        :param metadata: meta data for account (ie timestamp, user name, 
        access level etc...)
        :param storage: items/non metadata to store in account
        :return: account created
        """

        server = user.server
        if not self.account_exists(user, account_name):
            self._initialize_user_directory(user, server)
            metadata["created_at"] = datetime.utcnow().strftime(
                "%Y-%m-%d %H:%M:%S")
            account = {"metadata": metadata, "storage": storage}
            self._set_user_account(user, account_name, account)
            self._save_vault_data()
            return self.get_account(user, account_name)
        else:
            print("Account => {}.{}:{} already exists".format(server, user,
                                                              account_name))

    def _initialize_user_directory(self, user, server):
        """
        intiializes the dictionary for the user directory for a server
        :param user: discord user
        :param server: discord server
        :return: 
        """
        if server.id not in self.accounts:
            self.accounts[server.id] = {}
        if user.id not in self.accounts[server.id]:
            self.accounts[server.id][user.id] = {}

    def _set_user_account(self, user, account_name, account):
        """
        given a user, account name and account data, sets the account dictionary 
        to the given data
        :param user: discord user
        :param account_name: account key
        :param account: account data
        :return: 
        """
        self.accounts[user.server.id][user.id][account_name] = account

    def account_exists(self, user, account_name):
        server = user.server
        if self.accounts.get(server.id, {}).get(user.id, {}).get(account_name):
            return True
        return False

    def withdraw(self, user, account_name, withdraw_method):
        """
        withdraws data using a withdraw method
        :param user: discord user
        :param account_name: account for user
        :param withdraw_method: function object which carries out withdraw
        :return: 
        """
        account = self.get_account(user, account_name)
        try:
            withdraw_method(account)
            self._set_account(account)
            self._save_vault_data()
        # TODO what happens with security?
        except InvalidTransactionException as exception:
            print(exception)

    def deposit(self, user, account_name, deposit_method):
        """
        deposits data using a deposit method
        :param user: discord user
        :param account_name: account for user
        :param deposit_method: function object which carries out deposit
        :return: 
        """
        account = self.get_account(user, account_name)
        try:
            deposit_method(account)
            self._set_account(account)
            self._save_vault_data()
        except InvalidTransactionException as exception:
            print(exception)

    def transfer(self, send_user, send_account_name, recv_user,
                 recv_account_name, transfer_method):
        """
        transfers data between accounts using transfer method
        :param send_user: user to send
        :param send_account_name: account to send for user
        :param recv_user: user to recv
        :param recv_account_name: account to recv for recv user
        :param transfer_method: method by which transfer occurs
        :return: 
        """

        send_account = self.get_account(send_user, send_account_name)
        recv_account = self.get_account(recv_user, recv_account_name)
        try:
            transfer_method(send_account, recv_account)
            self._set_account(send_account)
            self._set_account(recv_account)
            self._save_vault_data()
        except InvalidTransactionException as exception:
            print(exception)

    def set_storage(self, user, account_name, storage):
        """
        sets the storage of the given user account 
        :param user: user to set storage of
        :param account_name: account name to set storage of
        :param storage: storage to set
        :return: 
        """
        account = self.get_account(user, account_name)
        try:
            account["storage"] = storage
            self._set_account(account)
            self._save_vault_data()
        except InvalidTransactionException as exception:
            print(exception)

    def set_metadata(self, user, account_name, metadata):
        """
        sets the metadata oaf a given user account
        :param user: discore user to set metadata of account of
        :param account_name: account to change metadata
        :param metadata: metadata to set
        :return: 
        """
        account = self.get_account(user, account_name)
        try:
            account["metadata"] = metadata
            self._set_account(account)
            self._save_vault_data()
        except InvalidTransactionException as exception:
            print(exception)

    def clear_account(self, user, account_name):
        self.accounts[user.server.id][user.id][account_name] = {}
        self._save_vault_data()

    def clear_user_accounts(self, user):
        self.accounts[user.server.id][user.id] = {}
        self._save_vault_data()

    def clear_server_accounts(self, server):
        self.accounts[server.id] = {}
        self._save_vault_data()

    def get_user_accounts(self, user):
        server = user.server
        raw_user_accounts = deepcopy(
            self.accounts.get(server.id, {}).get(user.id, {}))
        accounts = []
        for account_name, account in raw_user_accounts.items():
            account_tuple = self._create_account_tuple(server,
                                                       user,
                                                       account_name)
            accounts.append(account_tuple)

    def get_server_accounts(self, server):
        raw_server_accounts = deepcopy(self.accounts.get(server.id, {}))
        accounts = []
        for userid_key, user_accounts in raw_server_accounts.items():
            for account_name, account in user_accounts.items():
                temp_user = namedtuple("temp_user", "id, server")
                temp_user(userid_key, server)
                account_tuple = self._create_account_tuple(server,
                                                           temp_user,
                                                           account_name)
                accounts.append(account_tuple)
        return accounts

    def get_all_accounts(self):
        accounts = []
        for server_id, userids in self.accounts.items():
            server = self.bot.get_server(server_id)
            if server is None:
                # Servers that have since been left will be ignored
                # Same for users_id from the old bank format
                continue
            accounts.extend(self.get_server_accounts(server))
        return accounts

    def get_storage(self, user, account_name):
        account = self._get_account(user, account_name)
        return account["storage"]

    def get_metadata(self, user, account_name):
        account = self._get_account(user, account_name)
        return account["metadata"]

    def get_account(self, user, account_name):
        return self._create_account_tuple(user.server, user, account_name)

    def _set_account(self, account):
        """
        sets the account data to account param for the given user (assuming 
        account was created via namedtuple in _create_account_tuple)
        :param account: account to set
        :return: 
        """
        try:
            userid = account["userid"]
            server = account["server"]
            account_name = account["account_name"]
            self.accounts[server][userid][account_name] = account
        except KeyError as exception:
            print("Can't set account data: ", exception)

    def _create_account_tuple(self, server, user, account_name):
        """
        given a discord user and account name, retrieves the respective account
        from the vault as a named tuple of elements 
        :param user: discord user
        :param account_name: user account name
        :return: namedtuple(userid, server, name, member, created_at)
        """
        account_dict = self._get_account(user, account_name)
        account_dict["userid"] = user.id
        account_dict["server"] = server
        account_dict["name"] = account_name
        account_dict["member"] = server.get_member(user.id)
        account_dict["created_at"] = datetime.strptime(
            account_dict["metadata"]["created_at"], "%Y-%m-%d %H:%M:%S")
        Account = namedtuple("Account", list(account_dict.keys()))
        return Account(**account_dict)

    def _save_vault_data(self):
        """
        saves current dictionary data for accounts
        :return: 
        """
        dataIO.save_json(self.vault_path, self.accounts)

    def _get_account(self, user, account_name):
        """
        returns the copy of the user information in the loaded locker 
        self.accounts.  If the user at the given user server id is not found,
        returns a "No account exception"
        :param user: 
        :return: loaded json data of user information
        """
        server = user.server
        try:
            return deepcopy(self.accounts[server.id][user.id][account_name])
        except KeyError as exception:
            print("No account found: ", exception)

    def _get_user_accounts(self, user):
        """
        retrieves the dictionary object representing the accounts this user owns
        on the given server
        :param user: discord user
        :return: user accounts dictionary
        """
        return self.accounts[user.server.id][user.id]


def create_folder_if_none(folder_path):
    if not os.path.exists(folder_path):
        print("Creating {} folder...".format(folder_path))
        os.makedirs(folder_path)


def create_file_if_none(file_path):
    if not dataIO.is_valid_json(file_path):
        print("Creating default {}...".format(file_path))
        dataIO.save_json(file_path, {})


class Vault:
    def __init__(self, bot):
        self.bot = bot
        self.InvalidTransactionException = InvalidTransactionException
        self.cog_list = ['a', 'b']

    def get_vault(self, vault_path, folder_path, file_path, cogID):
        self.cog_list.append(cogID)
        create_folder_if_none(folder_path)
        create_file_if_none(file_path)
        return VaultClass(self.bot, vault_path)

    @staticmethod
    def make_transaction_exception(user_item_dict):
        raise InvalidTransactionException(user_item_dict)

    @commands.group(name="vault", pass_context=True)
    async def _vault(self, ctx):
        """Vault operations"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @_vault.command(pass_context=True, no_pm=True)
    async def coglist(self, ctx):
        """lists cogs currently using this vault"""
        await self.bot.say(("current cogs using vault: " + str(self.coglist)))


def setup(bot):
    global logger
    logger = logging.getLogger("red.vault")
    create_folder_if_none('data/vault')
    create_file_if_none('data/vault/vaultlogger.log')
    if logger.level == 0:
        # Prevents the logger from being loaded again in case of module reload
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler(filename='data/vault/vaultlogger.log',
                                      encoding='utf-8', mode='a')
        handler.setFormatter(logging.Formatter('%(asctime)s %(message)s',
                                               datefmt="[%d/%m/%Y %H:%M]"))
        logger.addHandler(handler)
    bot.add_cog(Vault(bot))
