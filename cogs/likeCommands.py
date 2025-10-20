import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
from datetime import datetime, timedelta
import json
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()
API_URL=os.getenv("API_URL")
CONFIG_FILE = "like_channels.json"

class LikeCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_host =API_URL
        self.config_data = self.load_config()
        self.cooldowns = {}
        self.session = aiohttp.ClientSession()
        self.auto_like_tasks = {}  # Store auto-like tasks


    def load_config(self):
        default_config = {
            "servers": {}
        }
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    loaded_config = json.load(f)
                    loaded_config.setdefault("servers", {})
                    return loaded_config
            except json.JSONDecodeError:
                print(f"WARNING: The configuration file '{CONFIG_FILE}' is corrupt or empty. Resetting to default configuration.")
        self.save_config(default_config)
        return default_config

    def save_config(self, config_to_save=None):
        data_to_save = config_to_save if config_to_save is not None else self.config_data
        temp_file = CONFIG_FILE + ".tmp"
        with open(temp_file, 'w') as f:
            json.dump(data_to_save, f, indent=4)
        os.replace(temp_file, CONFIG_FILE)

    async def check_channel(self, ctx):
        if ctx.guild is None:
            return True
        guild_id = str(ctx.guild.id)
        like_channels = self.config_data["servers"].get(guild_id, {}).get("like_channels", [])
        return not like_channels or str(ctx.channel.id) in like_channels

    async def cog_load(self):
        pass

    def get_server_flag(self, server):
        """Get flag emoji for server region"""
        flags = {
            "IND": "🇮🇳",  # India
            "BD": "🇧🇩",   # Bangladesh
            "BR": "🇧🇷"    # Brazil
        }
        return flags.get(server.upper(), "🌍")

    def format_server_with_flag(self, server):
        """Format server name with flag"""
        flag = self.get_server_flag(server)
        return f"{server} {flag}"

    async def send_auto_like(self, uid, server, channel_id, user_id):
        """Send automatic like for auto-like command"""
        try:
            url = f"{self.api_host}/like?uid={uid}&server={server}"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        embed = discord.Embed(
                            title="🔄 AUTO LIKE SUCCESFULLY SENDED",
                            color=0x2ECC71 if data.get("status") == 1 else 0xE74C3C,
                            timestamp=datetime.now()
                        )
                        
                        if data.get("status") == 1:
                            # Create a more visually appealing embed for auto-like
                            embed.title = "🔄 AUTO LIKE SUCCESFULLY SENDED"
                            embed.description = (
                                "✅ Auto-like delivered successfully!\n"
                                "✨ Perfect execution!"
                            )
                            
                            # Player Info Section
                            embed.add_field(
                                name="👤 Player Info",
                                value=f"```\n[UID]     {uid}\n[Name]    {data.get('player', 'Unknown')}```",
                                inline=True
                            )
                            
                            # Server Region Section
                            embed.add_field(
                                name="🌐 Server Region",
                                value=f"```\n{self.format_server_with_flag(data.get('region', 'Unknown'))} Server```",
                                inline=True
                            )
                            
                            # Like Stats Section
                            likes_before = data.get('likes_before', 0)
                            likes_after = data.get('likes_after', 0)
                            likes_added = data.get('likes_added', 0)
                            
                            embed.add_field(
                                name="📊 Like Stats",
                                value=f"```\nBefore: {likes_before} likes\nAfter:  {likes_after} likes\nAdded:  {likes_added} likes```",
                                inline=False
                            )
                            
                            
                            # Promotional Banner
                            embed.add_field(
                                name="",
                                value="**INSTANT DELIVERY**",
                                inline=False
                            )
                        else:
                            embed.description = "This UID has already received the maximum likes today.\nAuto-like will try again in 24 hours."
                        
                        embed.set_footer(text=f"🔹 Auto-like executed • DEVOLOPED BY UNKNOWN X!TER")
                        embed.set_image(url="https://ibb.co.com/TM4kTbck")
                        file = discord.File("assets/banned.gif", filename="banned.gif")
                        embed.set_image(url="attachment://banned.gif")
                        await channel.send(f"<@{user_id}>", embed=embed)
        except Exception as e:
            print(f"Error in auto-like for UID {uid}: {e}")

    async def auto_like_loop(self, uid, server, channel_id, user_id):
        """Background loop for auto-like functionality"""
        while True:
            try:
                await asyncio.sleep(24 * 60 * 60)  # Wait 24 hours
                await self.send_auto_like(uid, server, channel_id, user_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in auto-like loop for UID {uid}: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour before retrying

    @commands.hybrid_command(name="setlikechannel", description="Sets the channels where the /like command is allowed.")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(channel="The channel to allow/disallow the /like command in.")
    async def set_like_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        if ctx.guild is None:
            await ctx.send("This command can only be used in a server.", ephemeral=True)
            return

        guild_id = str(ctx.guild.id)
        server_config = self.config_data["servers"].setdefault(guild_id, {})
        like_channels = server_config.setdefault("like_channels", [])

        channel_id_str = str(channel.id)

        if channel_id_str in like_channels:
            like_channels.remove(channel_id_str)
            self.save_config()
            await ctx.send(f"✅ Channel {channel.mention} has been **removed** from allowed channels for /like commands. The command is now **disallowed** there.", ephemeral=True)
        else:
            like_channels.append(channel_id_str)
            self.save_config()
            await ctx.send(f"✅ Channel {channel.mention} is now **allowed** for /like commands. The command will **only** work in specified channels if any are set.", ephemeral=True)

    @commands.hybrid_command(name="like", description="Sends likes to a Free Fire player")
    @app_commands.describe(uid="Player UID (numbers only, minimum 6 characters)", server="Server region (IND, BD, BR)")
    async def like_command(self, ctx: commands.Context,server:str=None , uid: str = None):
        is_slash = ctx.interaction is not None

        if uid and server is None:
            return await ctx.send("UID and server are required",delete_after=10)
        if not await self.check_channel(ctx):
            msg = "This command is not available in this channel. Please use it in an authorized channel."
            if is_slash:
                await ctx.response.send_message(msg, ephemeral=True)
            else:
                await ctx.reply(msg, mention_author=False)
            return

        user_id = ctx.author.id
        cooldown = 30
        if user_id in self.cooldowns:
            last_used = self.cooldowns[user_id]
            remaining = cooldown - (datetime.now() - last_used).seconds
            if remaining > 0:
                await ctx.send(f"Please wait {remaining} seconds before using this command again.", ephemeral=is_slash)
                return
        self.cooldowns[user_id] = datetime.now()

        if not uid.isdigit() or len(uid) < 6:
            await ctx.reply("Invalid UID. It must contain only numbers and be at least 6 characters long.", mention_author=False, ephemeral=is_slash)
            return

        # Validate server
        valid_servers = ["IND", "BD", "BR"]
        if server.upper() not in valid_servers:
            await ctx.reply(f"Invalid server. Must be one of: {', '.join(valid_servers)}", mention_author=False, ephemeral=is_slash)
            return

        try:
            async with ctx.typing():
                url = f"{self.api_host}/like?uid={uid}&server={server}"
                print(url)
                async with self.session.get(url ) as response:
                    if response.status == 404:
                        await self._send_player_not_found(ctx, uid)
                        return

                    if response.status != 200:
                        print(f"API Error: {response.status} - {await response.text()}")
                        await self._send_api_error(ctx)
                        return

                    data = await response.json()
                    embed = discord.Embed(
                        title="FREE FIRE LIKE",
                        color=0x2ECC71 if data.get("status") == 1 else 0xE74C3C,
                        timestamp=datetime.now()
                    )

                    if data.get("status") == 1:
                        # Create a more visually appealing embed
                        embed.title = "🎉 LIKE SUCCESS"
                        embed.description = (
                            "✅ Likes delivered successfully!\n"
                            "✨ Perfect execution!"
                        )
                        
                        # Player Info Section
                        embed.add_field(
                            name="👤 Player Info",
                            value=f"```\n[UID]     {uid}\n[Name]    {data.get('player', 'Unknown')}```",
                            inline=True
                        )
                        
                        # Server Region Section
                        embed.add_field(
                            name="🌐 Server Region",
                            value=f"```\n{self.format_server_with_flag(data.get('region', 'Unknown'))} Server```",
                            inline=True
                        )
                        
                        # Like Stats Section
                        likes_before = data.get('likes_before', 0)
                        likes_after = data.get('likes_after', 0)
                        likes_added = data.get('likes_added', 0)
                        
                        embed.add_field(
                            name="📊 Like Stats",
                            value=f"```\nBefore: {likes_before} likes\nAfter:  {likes_after} likes\nAdded:  {likes_added} likes```",
                            inline=False
                        )
                        
                        
                        # Promotional Banner
                        embed.add_field(
                            name="",
                            value="**INSTANT DELIVERY**",
                            inline=False
                        )
                    else:
                        embed.description = "This UID has already received the maximum likes today.\nPlease wait 24 hours and try again"

                    embed.set_footer(text=f"🔹 Requested by {ctx.author.display_name} • DEVOLOPED BY UNKNOWN X!TER")
                    embed.set_image(url="https://ibb.co.com/TM4kTbck")
                    file = discord.File("assets/banned.gif", filename="banned.gif")
                    embed.set_image(url="attachment://banned.gif")
                    await ctx.send(embed=embed, mention_author=True, ephemeral=is_slash)

        except asyncio.TimeoutError:
            await self._send_error_embed(ctx, "Timeout", "The server took too long to respond.", ephemeral=is_slash)
        except Exception as e:
            print(f"Unexpected error in like_command: {e}")
            await self._send_error_embed(ctx, "Critical Error", "An unexpected error occurred. Please try again later.", ephemeral=is_slash)

    @commands.hybrid_command(name="auto_like", description="Automatically sends likes to a Free Fire player every 24 hours")
    @app_commands.describe(uid="Player UID (numbers only, minimum 6 characters)", server="Server region (IND, BD, BR)")
    async def auto_like_command(self, ctx: commands.Context, uid: str, server: str):
        is_slash = ctx.interaction is not None
        
        if not await self.check_channel(ctx):
            msg = "This command is not available in this channel. Please use it in an authorized channel."
            if is_slash:
                await ctx.response.send_message(msg, ephemeral=True)
            else:
                await ctx.reply(msg, mention_author=False)
            return

        # Validate UID
        if not uid.isdigit() or len(uid) < 6:
            await ctx.reply("Invalid UID. It must contain only numbers and be at least 6 characters long.", mention_author=False, ephemeral=is_slash)
            return

        # Validate server
        valid_servers = ["IND", "BD", "BR"]
        if server.upper() not in valid_servers:
            await ctx.reply(f"Invalid server. Must be one of: {', '.join(valid_servers)}", mention_author=False, ephemeral=is_slash)
            return

        server = server.upper()
        task_key = f"{uid}_{server}_{ctx.channel.id}"

        # Check if auto-like is already running for this UID+server+channel
        if task_key in self.auto_like_tasks:
            await ctx.reply(f"❌ Auto-like is already running for UID `{uid}` in server `{server}` in this channel.", mention_author=False, ephemeral=is_slash)
            return

        try:
            async with ctx.typing():
                # Test the API first
                url = f"{self.api_host}/like?uid={uid}&server={server}"
                async with self.session.get(url) as response:
                    if response.status == 404:
                        await self._send_player_not_found(ctx, uid)
                        return
                    if response.status != 200:
                        await self._send_api_error(ctx)
                        return

                # Start the auto-like task
                task = asyncio.create_task(self.auto_like_loop(uid, server, ctx.channel.id, ctx.author.id))
                self.auto_like_tasks[task_key] = task

                # Send confirmation embed
                embed = discord.Embed(
                    title="🔄 AUTO LIKE ADDED SUCCESFULLY",
                    color=0x2ECC71,
                    timestamp=datetime.now()
                )
                embed.description = (
                    f"**UID:** {uid}\n"
                    f"**Server:** {self.format_server_with_flag(server)}\n"
                    f"**Channel:** {ctx.channel.mention}\n"
                    f"**Started by:** {ctx.author.mention}\n\n"
                    f"✅ Auto-like is now active!\n"
                    f"🕐 Next like will be sent in 24 hours\n"
                    f"🔄 This will continue until the bot is restarted"
                )
                embed.set_footer(text="**DEVOLOPED BY UNKNOWN X!TER**")
                embed.set_image(url="https://ibb.co.com/TM4kTbck")
                file = discord.File("assets/banned.gif", filename="banned.gif")
                embed.set_image(url="attachment://banned.gif
                await ctx.send(embed=embed, mention_author=True, ephemeral=is_slash)

        except Exception as e:
            print(f"Error starting auto-like: {e}")
            await self._send_error_embed(ctx, "Error", "Failed to start auto-like. Please try again later.", ephemeral=is_slash)

    @commands.hybrid_command(name="stop_auto_like", description="Stops auto-like for a specific UID and server")
    @app_commands.describe(uid="Player UID to stop auto-like for", server="Server region")
    async def stop_auto_like_command(self, ctx: commands.Context, uid: str, server: str):
        is_slash = ctx.interaction is not None
        
        server = server.upper()
        task_key = f"{uid}_{server}_{ctx.channel.id}"

        if task_key not in self.auto_like_tasks:
            await ctx.reply(f"❌ No auto-like found for UID `{uid}` in server `{server}` in this channel.", mention_author=False, ephemeral=is_slash)
            return

        try:
            # Cancel the task
            task = self.auto_like_tasks[task_key]
            task.cancel()
            del self.auto_like_tasks[task_key]

            embed = discord.Embed(
                title="🛑 AUTO LIKE STOPPED",
                color=0xE74C3C,
                timestamp=datetime.now()
            )
            embed.description = (
                f"**UID:** {uid}\n"
                f"**Server:** {self.format_server_with_flag(server)}\n"
                f"**Channel:** {ctx.channel.mention}\n"
                f"**Stopped by:** {ctx.author.mention}\n\n"
                f"✅ Auto-like has been stopped successfully!"
            )
            embed.set_footer(text="**DEVOLOPED BY UNKNOWN X!TER**")
            
            await ctx.send(embed=embed, mention_author=True, ephemeral=is_slash)

        except Exception as e:
            print(f"Error stopping auto-like: {e}")
            await self._send_error_embed(ctx, "Error", "Failed to stop auto-like.", ephemeral=is_slash)

    @commands.hybrid_command(name="list_auto_likes", description="Shows all active auto-like tasks")
    async def list_auto_likes_command(self, ctx: commands.Context):
        is_slash = ctx.interaction is not None
        
        if not self.auto_like_tasks:
            await ctx.reply("❌ No active auto-like tasks found.", mention_author=False, ephemeral=is_slash)
            return

        embed = discord.Embed(
            title="📋 ACTIVE AUTO-LIKE TASKS",
            color=0x3498DB,
            timestamp=datetime.now()
        )
        
        task_list = []
        for task_key in self.auto_like_tasks.keys():
            uid, server, channel_id = task_key.rsplit('_', 2)
            channel = self.bot.get_channel(int(channel_id))
            channel_name = channel.name if channel else "Unknown Channel"
            task_list.append(f"**UID:** `{uid}` | **Server:** {self.format_server_with_flag(server)} | **Channel:** #{channel_name}")

        embed.description = "\n".join(task_list) if task_list else "No active tasks"
        embed.set_footer(text="**DEVOLOPED BY UNKNOWN X!TER**")
        await ctx.send(embed=embed, mention_author=True, ephemeral=is_slash)

    async def _send_player_not_found(self, ctx, uid):
        embed = discord.Embed(title="Player Not Found", description=f"The UID {uid} does not exist or is not accessible.", color=0xE74C3C)
        embed.add_field(name="Tip", value="Make sure that:\n- The UID is correct\n- The player is not private", inline=False)
        try:
            if ctx.interaction and not ctx.interaction.response.is_done():
                await ctx.send(embed=embed, ephemeral=True)
            elif not ctx.interaction:
                await ctx.send(embed=embed)
        except Exception as e:
            print(f"Failed to send player not found embed: {e}")
        
    async def _send_api_error(self, ctx):
        embed = discord.Embed(title="⚠️ Service Unavailable", description="The Free Fire API is not responding at the moment.", color=0xF39C12)
        embed.add_field(name="Solution", value="Try again in a few minutes.", inline=False)
        try:
            if ctx.interaction and not ctx.interaction.response.is_done():
                await ctx.send(embed=embed, ephemeral=True)
            elif not ctx.interaction:
                await ctx.send(embed=embed)
        except Exception as e:
            print(f"Failed to send API error embed: {e}")

    async def _send_error_embed(self, ctx, title, description, ephemeral=True):
        embed = discord.Embed(title=f"❌ {title}", description=description, color=discord.Color.red(), timestamp=datetime.now())
        embed.set_footer(text="An error occurred.")
        try:
            if ctx.interaction and not ctx.interaction.response.is_done():
                await ctx.send(embed=embed, ephemeral=ephemeral)
            elif not ctx.interaction:
                await ctx.send(embed=embed)
        except Exception as e:
            print(f"Failed to send error embed: {e}")

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())

async def setup(bot):
    await bot.add_cog(LikeCommands(bot))
