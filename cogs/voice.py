import discord
from discord.ext import commands
import json
from pathlib import Path

class VoiceChannels(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.create_channel_id = config['create_channel_id']
        self.blocked_role_id = config['blocked_role_id']
        self.default_role_id = config['default_role_id']
        self.temp_channels_path = Path(__file__).parent.parent / 'data' / 'temp_channels.json'
        self.temp_channels = self.load_channels()
        
    def load_channels(self):
        try:
            with open(self.temp_channels_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
            
    def save_channels(self):
        with open(self.temp_channels_path, 'w') as f:
            json.dump(self.temp_channels, f)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        # Handle channel creation
        if after.channel and after.channel.id == self.create_channel_id:
            # Create channel permissions
            overwrites = {
                member: discord.PermissionOverwrite(move_members=True, manage_channels=True),
                member.guild.get_role(self.blocked_role_id): discord.PermissionOverwrite(view_channel=False),
                member.guild.get_role(self.default_role_id): discord.PermissionOverwrite(view_channel=True, connect=True)
            }
            
            # Create new channel
            new_channel = await member.guild.create_voice_channel(
                name=f"{member.name}'s Channel",
                category=after.channel.category,
                position=after.channel.position + 1,  # This doesn't always work reliably
                user_limit=10,
                overwrites=overwrites
            )
            
            # Force position update after creation
            await new_channel.edit(position=after.channel.position + 1)
            
            # Move member to new channel
            await member.move_to(new_channel)
            
            # Save channel info
            self.temp_channels[str(new_channel.id)] = {
                "owner_id": member.id,
                "created_at": discord.utils.utcnow().timestamp()
            }
            self.save_channels()

        # Handle channel deletion
        if before.channel and str(before.channel.id) in self.temp_channels:
            if len(before.channel.members) == 0:
                await before.channel.delete()
                del self.temp_channels[str(before.channel.id)]
                self.save_channels()

    @commands.Cog.listener()
    async def on_ready(self):
        # Clean up empty channels on startup
        for guild in self.bot.guilds:
            for channel_id in list(self.temp_channels.keys()):
                channel = guild.get_channel(int(channel_id))
                if channel and len(channel.members) == 0:
                    await channel.delete()
                    del self.temp_channels[channel_id]
            self.save_channels()

async def setup(bot):
    config = bot.config  # Assuming the config is stored in the bot instance
    await bot.add_cog(VoiceChannels(bot, config))