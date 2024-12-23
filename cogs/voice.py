import discord
from discord.ext import commands
import json
from pathlib import Path
import asyncio
from typing import Dict, Optional

class VoiceChannels(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.create_channel_id = config['create_channel_id']
        self.blocked_role_id = config['blocked_role_id']
        self.default_role_id = config['default_role_id']
        self.temp_channels_path = Path(__file__).parent.parent / 'data' / 'temp_channels.json'
        self.temp_channels = self.load_channels()
        self.channel_creation_cooldown: Dict[int, float] = {}
        self.COOLDOWN_DURATION = 5.0  # Seconds between channel creations
        
    def load_channels(self):
        try:
            with open(self.temp_channels_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
            
    def save_channels(self):
        with open(self.temp_channels_path, 'w') as f:
            json.dump(self.temp_channels, f)

    async def create_voice_channel(self, member: discord.Member, category: discord.CategoryChannel) -> Optional[discord.VoiceChannel]:
        try:
            overwrites = {
                member: discord.PermissionOverwrite(move_members=True, manage_channels=True),
                member.guild.get_role(self.blocked_role_id): discord.PermissionOverwrite(view_channel=False),
                member.guild.get_role(self.default_role_id): discord.PermissionOverwrite(view_channel=True, connect=True)
            }
            
            new_channel = await member.guild.create_voice_channel(
                name=f"{member.name}'s Channel",
                category=category,
                position=category.channels[-1].position + 1,
                user_limit=10,
                overwrites=overwrites,
                reason=f"Temporary voice channel for {member.name}"
            )
            
            await asyncio.sleep(0.5)  # Brief delay for position update
            await new_channel.edit(position=category.channels[-1].position)
            
            return new_channel
        except discord.HTTPException:
            await asyncio.sleep(1)  # Rate limit backoff
            return None

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if after.channel and after.channel.id == self.create_channel_id:
            current_time = discord.utils.utcnow().timestamp()
            last_creation = self.channel_creation_cooldown.get(member.id, 0)
            
            if current_time - last_creation < self.COOLDOWN_DURATION:
                await asyncio.sleep(self.COOLDOWN_DURATION - (current_time - last_creation))
            
            new_channel = await self.create_voice_channel(member, after.channel.category)
            if new_channel:
                self.channel_creation_cooldown[member.id] = current_time
                await member.move_to(new_channel)
                
                self.temp_channels[str(new_channel.id)] = {
                    "owner_id": member.id,
                    "created_at": current_time
                }
                self.save_channels()

        if before.channel and str(before.channel.id) in self.temp_channels:
            if len(before.channel.members) == 0:
                try:
                    await before.channel.delete(reason="Temporary channel cleanup")
                    del self.temp_channels[str(before.channel.id)]
                    self.save_channels()
                except discord.HTTPException:
                    await asyncio.sleep(1)  # Rate limit backoff

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            for channel_id in list(self.temp_channels.keys()):
                channel = guild.get_channel(int(channel_id))
                if channel and len(channel.members) == 0:
                    try:
                        await channel.delete(reason="Startup cleanup")
                        del self.temp_channels[channel_id]
                    except discord.HTTPException:
                        await asyncio.sleep(1)
            self.save_channels()

async def setup(bot):
    config = bot.config
    await bot.add_cog(VoiceChannels(bot, config))
