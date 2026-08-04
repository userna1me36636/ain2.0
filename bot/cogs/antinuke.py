from __future__ import annotations

import datetime as dt
import time
from collections import defaultdict, deque

import discord
from discord import app_commands
from discord.ext import commands

from bot.core.checks import app_admin
from bot.core.utils import embed
from bot.core.utils import embed


class AntiNuke(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.events: dict[tuple[int, int, str], deque[float]] = defaultdict(lambda: deque(maxlen=10))

    antinuke = app_commands.Group(name="antinuke", description="Protect the server from destructive actions")

    @antinuke.command(name="configure", description="Configure anti-nuke protection")
    @app_admin()
    async def configure(self, interaction: discord.Interaction, event: str, enabled: bool, threshold: int = 3, seconds: int = 30, punishment: str = "strip_roles") -> None:
        settings = await self.bot.db.get_settings(interaction.guild_id, self.bot.settings.default_prefix)
        data = settings.get("antinuke", {})
        data[event] = {"enabled": enabled, "threshold": threshold, "seconds": seconds, "punishment": punishment}
        await self.bot.db.set_settings_value(interaction.guild_id, "antinuke", data, self.bot.settings.default_prefix)
        await interaction.response.send_message(f"Anti-nuke `{event}` updated.", ephemeral=True)

    @antinuke.command(name="enable", description="Enable anti-nuke protection")
    @app_admin()
    async def enable(self, interaction: discord.Interaction) -> None:
        await self.bot.db.set_settings_value(interaction.guild_id, "antinuke_enabled", True, self.bot.settings.default_prefix)
        await interaction.response.send_message("Anti-nuke enabled.", ephemeral=True)

    @antinuke.command(name="disable", description="Disable anti-nuke protection")
    @app_admin()
    async def disable(self, interaction: discord.Interaction) -> None:
        await self.bot.db.set_settings_value(interaction.guild_id, "antinuke_enabled", False, self.bot.settings.default_prefix)
        await interaction.response.send_message("Anti-nuke disabled.", ephemeral=True)

    @antinuke.command(name="status", description="Show anti-nuke status")
    @app_admin()
    async def status(self, interaction: discord.Interaction) -> None:
        settings = await self.bot.db.get_settings(interaction.guild_id, self.bot.settings.default_prefix)
        await interaction.response.send_message(embed=embed("Anti-Nuke Status", f"Enabled: `{settings.get('antinuke_enabled', True)}`"), ephemeral=True)

    @antinuke.command(name="whitelist", description="Whitelist a user or role from anti-nuke")
    @app_admin()
    async def whitelist(self, interaction: discord.Interaction, target_id: str) -> None:
        settings = await self.bot.db.get_settings(interaction.guild_id, self.bot.settings.default_prefix)
        data = settings.get("antinuke_whitelist", [])
        value = int(target_id)
        if value not in data:
            data.append(value)
        await self.bot.db.set_settings_value(interaction.guild_id, "antinuke_whitelist", data, self.bot.settings.default_prefix)
        await interaction.response.send_message("Whitelist updated.", ephemeral=True)

    async def actor_from_audit(self, guild: discord.Guild, action: discord.AuditLogAction) -> discord.Member | None:
        async for entry in guild.audit_logs(limit=1, action=action):
            if entry.user and isinstance(entry.user, discord.Member):
                return entry.user
            if entry.user:
                member = guild.get_member(entry.user.id)
                return member
        return None

    async def record(self, guild: discord.Guild, event: str, action: discord.AuditLogAction) -> None:
        actor = await self.actor_from_audit(guild, action)
        if actor is None or actor.id == guild.owner_id or actor.bot:
            return
        settings = await self.bot.db.get_settings(guild.id, self.bot.settings.default_prefix)
        if settings.get("antinuke_enabled", True) is False:
            return
        if actor.id in settings.get("antinuke_whitelist", []) or any(r.id in settings.get("antinuke_whitelist", []) for r in actor.roles):
            return
        cfg = settings.get("antinuke", {}).get(event, {"enabled": True, "threshold": 3, "seconds": 30, "punishment": "strip_roles"})
        if not cfg.get("enabled", True):
            return
        now = time.monotonic()
        key = (guild.id, actor.id, event)
        self.events[key].append(now)
        if len(self.events[key]) >= int(cfg.get("threshold", 3)) and now - self.events[key][0] <= int(cfg.get("seconds", 30)):
            await self.punish(actor, cfg.get("punishment", "strip_roles"), event)

    async def punish(self, member: discord.Member, punishment: str, event: str) -> None:
        reason = f"Anti-nuke triggered: {event}"
        try:
            if punishment == "ban":
                await member.ban(reason=reason)
            elif punishment == "kick":
                await member.kick(reason=reason)
            elif punishment == "timeout":
                await member.timeout(discord.utils.utcnow() + dt.timedelta(hours=1), reason=reason)
            elif punishment == "strip_roles":
                roles = [r for r in member.roles if not r.managed and r != member.guild.default_role]
                await member.remove_roles(*roles, reason=reason)
        except discord.HTTPException:
            pass
        await self.bot.db.execute("INSERT INTO audit_events(guild_id,actor_id,event,data) VALUES(?,?,?,?)", member.guild.id, member.id, "antinuke", f'{{"event":"{event}","punishment":"{punishment}"}}')

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        await self.record(channel.guild, "channel_delete", discord.AuditLogAction.channel_delete)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        await self.record(channel.guild, "channel_create", discord.AuditLogAction.channel_create)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role) -> None:
        await self.record(role.guild, "role_delete", discord.AuditLogAction.role_delete)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role) -> None:
        await self.record(role.guild, "role_create", discord.AuditLogAction.role_create)

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.abc.GuildChannel) -> None:
        await self.record(channel.guild, "webhook_update", discord.AuditLogAction.webhook_create)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AntiNuke(bot))
