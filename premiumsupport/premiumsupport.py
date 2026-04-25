import asyncio
import datetime

import discord
from discord.ext import commands

from bot import ModmailBot
from core import checks
from core.models import PermissionLevel


# 🔴 CHANGE THIS
GUILD_ID = 123456789012345678  # MAIN SERVER (roles yahin se check honge)


class PremiumSupport(commands.Cog):
    """Special support for Premium members."""

    def __init__(self, bot: ModmailBot):
        self.bot = bot
        self.db = bot.plugin_db.get_partition(self)

        self.roles = []
        self.message = ""
        self.mention = ""
        self.category = 0

        asyncio.create_task(self._set_val())

    # ---------------- DATABASE ----------------

    async def _update_db(self):
        await self.db.find_one_and_update(
            {"_id": "config"},
            {
                "$set": {
                    "roles": self.roles,
                    "message": self.message,
                    "mention": self.mention,
                    "category": self.category,
                }
            },
            upsert=True,
        )

    async def _set_val(self):
        config = await self.db.find_one({"_id": "config"})
        if config:
            self.roles = config.get("roles", [])
            self.message = config.get("message", "")
            self.mention = config.get("mention", "")
            self.category = config.get("category", 0)

    # ---------------- MAIN LOGIC ----------------

    @commands.Cog.listener()
    async def on_thread_ready(self, thread, creator, category, initial_message):

        # get user id
        if isinstance(thread.recipient, int):
            user_id = thread.recipient
        else:
            user_id = thread.recipient.id

        # 🔥 FETCH MAIN SERVER (NOT CACHE)
        try:
            main_guild = await self.bot.fetch_guild(GUILD_ID)
            member = await main_guild.fetch_member(user_id)
        except (discord.NotFound, discord.Forbidden):
            return  # user main server me nahi / bot no access

        # premium role check
        if not any(role.id in self.roles for role in member.roles):
            return

        # fake message object (modmail requirement)
        class Author:
            id = user_id
            roles = []

        class Msg:
            content = self.message
            author = Author
            created_at = datetime.datetime.utcnow()
            id = initial_message.id
            attachments = []
            stickers = []

        # auto reply
        if Msg.content:
            await thread.send(
                Msg,
                destination=member,
                from_mod=True,
                anonymous=True,
            )

        # mention staff
        if self.mention:
            await thread.channel.send(self.mention)

        # move category (INBOX SERVER)
        if self.category:
            target_category = discord.utils.get(
                thread.channel.guild.categories, id=self.category
            )
            if target_category:
                await thread.channel.move(
                    category=target_category,
                    reason="Premium support",
                )

    # ---------------- COMMANDS ----------------

    @checks.has_permissions(PermissionLevel.ADMIN)
    @commands.group(invoke_without_command=True, aliases=["pc"])
    async def premiumconfig(self, ctx):
        embed = discord.Embed(
            title="Premium Support Config",
            colour=self.bot.main_color,
        )
        embed.add_field(name="Premium Roles", value=self.roles or "None", inline=False)
        embed.add_field(
            name="Auto Reply Message",
            value=self.message or "None",
            inline=False,
        )
        embed.add_field(
            name="Mention Message",
            value=self.mention or "None",
            inline=False,
        )
        embed.add_field(
            name="Premium Category ID",
            value=self.category or "None",
            inline=False,
        )
        await ctx.send(embed=embed)

    @checks.has_permissions(PermissionLevel.ADMIN)
    @premiumconfig.command(aliases=["role"])
    async def roles(self, ctx, roles: commands.Greedy[discord.Role]):
        self.roles = [role.id for role in roles]
        await self._update_db()
        await ctx.send(f"✅ Premium roles set: `{self.roles}`")

    @checks.has_permissions(PermissionLevel.ADMIN)
    @premiumconfig.command()
    async def message(self, ctx, *, message):
        self.message = message
        await self._update_db()
        await ctx.send("✅ Premium message updated")

    @checks.has_permissions(PermissionLevel.ADMIN)
    @premiumconfig.command()
    async def mention(self, ctx, *, message):
        self.mention = message
        await self._update_db()
        await ctx.send("✅ Mention message updated")

    @checks.has_permissions(PermissionLevel.ADMIN)
    @premiumconfig.command()
    async def category(self, ctx, category_id: int = 0):
        self.category = category_id
        await self._update_db()
        await ctx.send(f"✅ Premium category set to `{category_id}`")


async def setup(bot):
    await bot.add_cog(PremiumSupport(bot))
