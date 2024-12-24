from discord.ext import commands

class Basic(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command()
    async def ping(self, ctx):
        await ctx.send(f'Pong! Latency: {round(self.bot.latency * 1000)}ms')

async def setup(bot):
    await bot.add_cog(Basic(bot))
