import discord

import players

import asyncio
import sys

sys.path.append("")
from settings import Settings

sys.path.append('source/data')
from dictionaries import channels
from dictionaries import start_role_messages
from dictionaries import game_messages
from enums import Game_Phase

sys.path.append('source/utility')
from misc import get_dm_channel
from misc import get_participant_role
from misc import get_dead_role
from misc import set_nickname
from misc import ordinalize
import confirmations

game_phase = Game_Phase.Null
day_number = 0
previous_day_length = 0
timer = 0
second_count = 0
end_setup = True
run_game = False
next_phase = False

pause_timer = False

participant_role = None
dead_role = None

# Sets up the game and starts it
async def on_start(user, fallback_channel):
    global channels
    async with fallback_channel.typing():
        await on_reset()

    # Throw error if channels are not setup
    try:
        for i in channels:
            if channels[i] == None:
                raise Exception("Invalid setup.")

    except:
        embed = discord.Embed(color = 0xff0000, title = "Error in Starting Game", description = "The channels have not been setup. Failed to start the game.")
        await fallback_channel.send(embed = embed)
        return

    # Throw error if not enough players
    if len(players.Player_Manager.players) < Settings.get_min_player_count():
        embed = discord.Embed(color = 0xff0000, title = "Error in Starting Game", description = "There are not enough players to properly run the game without errors. Failed to start the game.")
        await fallback_channel.send(embed = embed)
        return

    # Set up game
    try:
        global game_phase
        game_phase = Game_Phase.Starting

        # Set moderator
        players.Player_Manager.moderator = user

        # Distribute roles
        players.Player_Manager.distribute_roles()
        dm = await get_dm_channel(user)
        await dm.send(embed = players.Player_Manager.list_players_with_roles())

        # Confirm roles
        await asyncio.sleep(1)
        message = await fallback_channel.send("Roles have been distributed, and have been privately sent to {}. Are you okay with this role distribution? You have 5 minutes to confirm this distribution.".format(user.display_name))
        await confirmations.confirm_roles(fallback_channel, message, user)

    except Exception as e:
        await on_reset()
        embed = discord.Embed(color = 0xff0000, title = "Error in Starting Game", description = "There was an error in starting the game:\n{}\n\nThe game has been reset.".format(e))
        await fallback_channel.send(embed = embed)

# Called after user confirms role distribution
async def continue_start(channel):
    await asyncio.sleep(0.5)
    try:
        async with channel.typing():

            # Enable permissions for channel category
            everyone = channels["meeting"].guild.default_role
            try:
                await channels["meeting"].category.set_permissions(everyone, read_message_history = True, read_messages = True, send_messages = True)
            except:
                None

            # Close channels
            await channels["meeting"].set_permissions(everyone, read_messages = True, send_messages = False)
            await channels["wolves"].set_permissions(everyone, read_messages = False, send_messages = False)
            await channels["snake"].set_permissions(everyone, read_messages = False, send_messages = False)
            await channels["spider"].set_permissions(everyone, read_messages = False, send_messages = False)
            await channels["dead"].set_permissions(everyone, read_messages = False, send_messages = False)
            await channels["voice_meeting"].set_permissions(everyone, view_channel = True)
            await channels["voice_wolves"].set_permissions(everyone, view_channel = False)

            # Set moderator's permissions
            moderator = players.Player_Manager.moderator
            for i in channels:
                if "voice" in i: # Voice channels
                    await channels[i].set_permissions(moderator, view_channel = True)
                else: # Text channels
                    await channels[i].set_permissions(moderator, read_messages = True, send_messages = True)
            # Try to set moderator nickname
            try:
                await moderator.edit(nick = "!{}".format(moderator.display_name))
            except:
                None

            # Send start message
            meeting_hall = channels["meeting"]
            await meeting_hall.send(game_messages["start"])
            await asyncio.sleep(1)

            # DM players
            await dm_roles()
            await channel.send("Humans, monkeys, and the crow have been sent their roles...")

            # Setup channels
            await asyncio.sleep(0.5)
            await setup_channels_perms(channel)

            # Give players role
            global participant_role, dead_role
            participant_role = await get_participant_role()
            dead_role = await get_dead_role()
            for player in players.Player_Manager.players:
                await player.user.add_roles(participant_role)

                # Fix player nicknames
                try:
                    await player.user.edit(nick = player.user.display_name.replace("死", "").replace("見", "").strip())
                except:
                    None

                await asyncio.sleep(0.1)

            await channel.send("Setup complete. The first morning will start in 15 minutes.\nUse the `$next` command to skip the timer and start the first morning.")

        # Timer
        global end_setup
        end_setup = False
        timer = 0
        max_timer = 15 * 60
        while not end_setup:
            await asyncio.sleep(1)
            timer += 1
            if timer >= max_timer:
                end_setup = True
        await channel.send("**GAME IS STARTING**")
        await asyncio.sleep(2)

        # Run game
        global run_game
        run_game = True
        while run_game:
            # ---------------------

            await morning()
            await asyncio.sleep(0.1)

            # Check win condition

            # Check exit game
            if not run_game:
                break

            # ---------------------

            await day()
            await asyncio.sleep(0.1)

            # Check win condition after lynching

            # Check exit game
            if not run_game:
                break

            # ---------------------

            await evening()
            await asyncio.sleep(0.1)

            # Check win condition

            # Check exit game
            if not run_game:
                break

            # ---------------------

            await night()
            await asyncio.sleep(0.1)

            # Check exit game
            if not run_game:
                break

        # End game

    # Error
    except Exception as e:
        #await on_reset()
        embed = discord.Embed(color = 0xff0000, title = "Game Crashed", description = "The game has crashed due to an error in the game:\n{}.\n\nUse the `$reset` command to reset the game.".format(e))
        await channel.send(embed = embed)

async def dm_roles():
    await asyncio.sleep(1)

    # DM players - humans
    for player in players.Player_Manager.humans:
        dm = await get_dm_channel(player.user)
        await dm.send(start_role_messages["human"])
    await asyncio.sleep(0.1)

    # DM players - monkeys
    if len(players.Player_Manager.monkeys) > 0:
        dm = await get_dm_channel(players.Player_Manager.monkeys[0].user)
        await dm.send(start_role_messages["monkey"].format(players.Player_Manager.monkeys[1].name))
        await asyncio.sleep(0.1)
        
        dm = await get_dm_channel(players.Player_Manager.monkeys[1].user)
        await dm.send(start_role_messages["monkey"].format(players.Player_Manager.monkeys[0].name))
        await asyncio.sleep(0.1)
    
    # DM players - crow
    if players.Player_Manager.crow_alive():
        dm = await get_dm_channel(players.Player_Manager.crow.user)
        await dm.send(start_role_messages["crow"])
        await asyncio.sleep(0.1)
    
    # DM players - inu
    if players.Player_Manager.inu_alive():
        dm = await get_dm_channel(players.Player_Manager.inu.user)
        await dm.send(start_role_messages["inu"])
        await asyncio.sleep(0.1)
    
    # DM players - fox
    if players.Player_Manager.fox_alive():
        dm = await get_dm_channel(players.Player_Manager.fox.user)
        await dm.send(start_role_messages["fox"])
        await asyncio.sleep(0.1)

    # DM players - badger
    if players.Player_Manager.badger_alive():
        dm = await get_dm_channel(players.Player_Manager.badger.user)
        await dm.send(start_role_messages["human"])
        await asyncio.sleep(0.1)

async def setup_channels_perms(channel):
    global channels

    # Wolves
    mention_wolves = ""
    for wolf in players.Player_Manager.wolves:
        await channels["wolves"].set_permissions(wolf.user, read_messages = True, send_messages = False)
        mention_wolves += "{} ".format(wolf.user.mention)
        await asyncio.sleep(0.5)
    await asyncio.sleep(1)
    await channels["wolves"].send("{}\n\n{}".format(mention_wolves.strip(), start_role_messages["wolves"]))

    await asyncio.sleep(0.5)
    await channel.send("Wolves have been setup...")

    # Snake
    await channels["snake"].set_permissions(players.Player_Manager.snake.user, read_messages = True, send_messages = False)
    await asyncio.sleep(1)
    await channels["snake"].send("{}\n\n{}".format(players.Player_Manager.snake.user.mention, start_role_messages["snake"]))

    await asyncio.sleep(0.5)
    await channel.send("Snake has been setup...")

    # Spider
    await channels["spider"].set_permissions(players.Player_Manager.spider.user, read_messages = True, send_messages = False)
    await asyncio.sleep(1)
    await channels["spider"].send("{}\n\n{}".format(players.Player_Manager.spider.user.mention, start_role_messages["spider"]))

    await asyncio.sleep(0.5)
    await channel.send("Spider has been setup...")

# ---------------------------------------------------------------------------------

async def morning():
    await asyncio.sleep(0.5)
    global day_number, previous_day_length, game_phase
    day_number += 1
    game_phase = Game_Phase.Morning

    # TODO - Message crow

    meeting_hall = channels["meeting"]
    day_length = get_day_length()
    global participant_role
    # First morning
    if day_number == 1:
        await meeting_hall.send(game_messages["first_morning"].format(participant_role.mention, len(players.Player_Manager.wolves), day_length))

    # Other mornings
    else:
        # Days get shorter
        if day_length < previous_day_length:
            await meeting_hall.send(game_messages["morning_no_death_time_change"].format(participant_role.mention, ordinalize(day_number), day_length))

        # Days stay same
        else:
            await meeting_hall.send(game_messages["morning_no_death"].format(participant_role.mention, ordinalize(day_number), day_length))

    previous_day_length = day_length

    # Open meeting hall
    for player in players.Player_Manager.players:
        await channels["meeting"].set_permissions(player.user, read_messages = True, send_messages = True)
        await channels["voice_meeting"].set_permissions(player.user, view_channel = True, connect = True)

async def day():
    global next_phase, game_phase, timer, second_count, previous_day_length
    next_phase = False
    game_phase = Game_Phase.Day

    timer = previous_day_length * 60
    second_count = 0
    channel = channels["meeting"]

    # Meeting hall is opened during the morning

    # Timer
    global pause_timer
    while not next_phase:
        await asyncio.sleep(1)

        # Timer paused
        if pause_timer:
            continue

        # Increment timer
        timer -= 1
        second_count += 1

        # Check next phase or warnings
        if timer <= 0:
            next_phase = True
        else:
            await timer_warning(channel, timer)

    await channel.send(game_messages["day_end"])

async def evening():
    global next_phase, game_phase, timer, second_count
    next_phase = False
    game_phase = Game_Phase.Evening
    
    timer = 3 * 60
    second_count = 0
    channel = channels["meeting"]

    # Open channels
    if players.Player_Manager.snake_alive():
        await channels["snake"].set_permissions(players.Player_Manager.snake.user, read_messages = True, send_messages = True)
    if players.Player_Manager.spider_alive():
        await channels["spider"].set_permissions(players.Player_Manager.spider.user, read_messages = True, send_messages = True)

    # TODO - message snake and spider channels to have them do their thing

    # Timer
    global pause_timer
    while not next_phase:
        await asyncio.sleep(1)

        # Timer paused
        if pause_timer:
            continue

        # Increment timer
        timer -= 1
        second_count += 1

        # Check next phase or warnings
        if timer <= 0:
            next_phase = True
        else:
            await timer_warning(channel, timer, phase = "afternoon")

    await channel.send(game_messages["evening_end"])

    # Kick players from VC
    for user in channels["voice_meeting"].members:
        # Kick alive players
        try:
            if players.Player_Manager.has_player_id(user.id):
                await user.move_to(None)
                continue
        except Exception as e:
            await channels["moderator"].send("Error: {}".format(e))

    # Unmute dead players
    for user in channels["voice_meeting"].members:
        try:
            if players.Player_Manager.has_player_id(user.id, dead_players = True):
                await channels["voice_meeting"].set_permissions(user, view_channel = True, connect = True, speak = True)
                await user.edit(mute = False)
        except:
            None

    # Close channels
    for player in players.Player_Manager.players:
        await channels["meeting"].set_permissions(player.user, read_messages = True, send_messages = False)
        await channels["voice_meeting"].set_permissions(player.user, view_channel = True, connect = False)

    if players.Player_Manager.snake_alive():
        await channels["snake"].set_permissions(players.Player_Manager.snake.user, read_messages = True, send_messages = False)
    if players.Player_Manager.spider_alive():
        await channels["spider"].set_permissions(players.Player_Manager.spider.user, read_messages = True, send_messages = False)

async def night():
    global next_phase, game_phase, timer, second_count
    next_phase = False
    game_phase = Game_Phase.Night

    timer = 4 * 60
    second_count = 0
    channel = channels["wolves"]

    # Open channels
    mention_wolves = ""
    for wolf in players.Player_Manager.wolves:
        await channels["wolves"].set_permissions(wolf.user, read_messages = True, send_messages = True)
        await channels["voice_wolves"].set_permissions(wolf.user, view_channel = True, connect = True)
        mention_wolves += "{} ".format(wolf.user.mention)
        await asyncio.sleep(0.5)

    await channels["wolves"].send(game_messages["night_start"].format(mention_wolves.strip()))

    # Message badger on night 1
    global day_number
    if day_number == 1 and players.Player_Manager.badger_alive():
        dm = await get_dm_channel(players.Player_Manager.badger.user)
        await dm.send(start_role_messages["badger"].format(mention_wolves.strip()))
        await channels["moderator"].send("The badger, {}, has been sent their updated role.".format(players.Player_Manager.badger.user.mention))
        await asyncio.sleep(0.1)

    # Timer
    global pause_timer
    while not next_phase:
        await asyncio.sleep(1)

        # Timer paused
        if pause_timer:
            continue

        # Increment timer
        timer -= 1
        second_count += 1

        # Check next phase or warnings
        if timer <= 0:
            next_phase = True
        else:
            await timer_warning(channel, timer, phase = "night")

    await channel.send(game_messages["night_end"])

    # Close channels
    for wolf in players.Player_Manager.wolves:
        await channels["wolves"].set_permissions(wolf.user, read_messages = True, send_messages = False)
        await channels["voice_wolves"].set_permissions(wolf.user, view_channel = True, connect = False)
        await asyncio.sleep(0.1)

    # Mute dead players
    for user in channels["voice_meeting"].members:
        try:
            if players.Player_Manager.has_player_id(user.id, dead_players = True):
                await channels["voice_meeting"].set_permissions(user, view_channel = True, connect = True, speak = False)
                await user.edit(mute = True)
        except:
            None

# ---------------------------------------------------------------------------------

async def timer_warning(channel, timer, phase = "day"):
    if timer == 600: # 10 Minutes
        await channel.send("**10 minutes remain in the {}.**".format(phase))
    elif timer == 300: # 5 Minutes
        await channel.send("**5 minutes remain in the {}.**".format(phase))
    elif timer == 60: # 1 Minute
        await channel.send("**1 minute remains in the {}.**".format(phase))
    elif timer == 30: # 30 Seconds
        await channel.send("**30 seconds remain in the {}.**".format(phase))
    elif timer == 10: # 10 Seconds
        await channel.send("**10 seconds remain in the {}.**".format(phase))
    elif timer <= 5: # 5 Second countdown
        await channel.send("**{} second{} remaining.**".format(timer, "" if timer == 1 else "s"))

def get_day_length():
    player_count = len(players.Player_Manager.players)
    if player_count <= 4:
        return 5 # 1-4
    elif player_count <= 8:
        return 10 # 5-8
    elif player_count <= 12:
        return 15 # 9-12
    elif player_count <= 16:
        return 20 # 13-16
    elif player_count <= 20:
        return 25 # 17-20
    else:
        return 30 # 21+

# ---------------------------------------------------------------------------------

# Called by the reset command
async def reset_game(channel, clear_player_list = False):
    async with channel.typing():
        await on_reset(clear_player_list = clear_player_list)

        if clear_player_list:
            await channel.send("The game has been reset.")
        else:
            await channel.send("The game has been forcefully ended.")

# Resets the game; called whenever a reset is needed
async def on_reset(clear_player_list = False, fast_ver = False):
    global game_phase, day_number, previous_day_length, second_count, end_setup, run_game, next_phase, pause_timer, participant_role, dead_role
    game_phase = Game_Phase.Null
    day_number = 0
    previous_day_length = 0
    second_count = 0
    end_setup = True
    run_game = False
    next_phase = True

    pause_timer = False

    participant_role = None
    dead_role = None

    # Remove players from channels
    try:
        await channels["meeting"].edit(sync_permissions = True)
        await channels["wolves"].edit(sync_permissions = True)
        await channels["snake"].edit(sync_permissions = True)
        await channels["spider"].edit(sync_permissions = True)
        await channels["dead"].edit(sync_permissions = True)
        await channels["voice_meeting"].edit(sync_permissions = True)
        await channels["voice_wolves"].edit(sync_permissions = True)
    except:
        None

    # Fix user nicknames and unmute
    if not fast_ver:
        # Moderator
        try:
            await players.Player_Manager.moderator.edit(nick = players.Player_Manager.moderator.display_name.replace("!", ""))
        except:
            None
        # Players
        for player in players.Player_Manager.players:
            try:
                await set_nickname(player.user, clear = True)
                await player.user.edit(mute = False)
            except:
                None

    # Clear/reset player list
    if clear_player_list:
        players.Player_Manager.clear_players() # Clears player list
    else:
        players.Player_Manager.reset() # Resets but does not clear