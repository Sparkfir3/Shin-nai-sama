import discord

import sys
sys.path.append('source/data')
from dictionaries import channels

async def get_dm_channel(user):
    channel = user.dm_channel
    if channel == None:
        channel = await user.create_dm()
    return channel

async def get_participant_role():
    guild = channels["meeting"].guild
    role = discord.utils.get(guild.roles, name="Feast Participant")
    if role == None:
        return await guild.create_role(name = "Feast Participant")
    else:
        return role

async def get_dead_role():
    guild = channels["meeting"].guild
    role = discord.utils.get(guild.roles, name="Dead")
    if role == None:
        return await guild.create_role(name = "Dead")
    else:
        return role

def ordinalize(number):
    if number % 10 == 1:
        return "{}st".format(number)
    elif number % 10 == 2:
        return "{}nd".format(number)
    elif number % 10 == 3:
        return "{}rd".format(number)
    else:
        return "{}th".format(number)