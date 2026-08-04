from __future__ import annotations

import json

import discord
from discord import app_commands
from discord.ext import commands

from bot.core.checks import app_admin, has_guild_permissions
from bot.core.utils import embed


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    prefix = app_commands.Group(name="prefix", description="Manage server prefixes")
    config = app_commands.Group(name="config", description="Configure bot modules")

    @commands.command(name="prefix")
    @has_guild_permissions(manage_guild=True)
    async def prefix_command(self, ctx: commands.Context, new_prefix: str | None = None) -> None:
        """Show or change this server's prefix."""
        if ctx.guild is None:
            return
        if new_prefix is None:
            settings = await self.bot.db.get_settings(ctx.guild.id, self.bot.settings.default_prefix)
            await ctx.reply(f"Current prefix: `{settings['prefix']}`", mention_author=False)
            return
        await self.bot.db.set_prefix(ctx.guild.id, new_prefix[:12], self.bot.settings.default_prefix)
        await ctx.reply(f"Prefix changed to `{new_prefix[:12]}`.", mention_author=False)

    @prefix.command(name="set", description="Set the prefix for this server")
    @app_admin()
    async def slash_prefix_set(self, interaction: discord.Interaction, prefix: str) -> None:
        await self.bot.db.set_prefix(interaction.guild_id, prefix[:12], self.bot.settings.default_prefix)
        await interaction.response.send_message(f"Prefix changed to `{prefix[:12]}`.", ephemeral=True)

    @config.command(name="panel", description="Open the configuration overview")
    @app_admin()
    async def config_panel(self, interaction: discord.Interaction) -> None:
        settings = await self.bot.db.get_settings(interaction.guild_id, self.bot.settings.default_prefix)
        e = embed("Configuration")
        for key in sorted(k for k in settings if k != "prefix"):
            value = settings[key]
            if isinstance(value, (dict, list)):
                value = json.dumps(value)[:900]
            e.add_field(name=key, value=f"`{value}`", inline=False)
        e.add_field(name="prefix", value=f"`{settings['prefix']}`", inline=True)
        await interaction.response.send_message(embed=e, ephemeral=True)

    @config.command(name="set", description="Set a simple configuration value")
    @app_admin()
    async def config_set(self, interaction: discord.Interaction, key: str, value: str) -> None:
        if interaction.guild_id is None:
            return
        parsed: object
        lowered = value.lower()
        if lowered in {"true", "false"}:
            parsed = lowered == "true"
        else:
            try:
                parsed = int(value)
            except ValueError:
                parsed = value
        await self.bot.db.set_settings_value(interaction.guild_id, key, parsed, self.bot.settings.default_prefix)
        await interaction.response.send_message(f"`{key}` updated.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
