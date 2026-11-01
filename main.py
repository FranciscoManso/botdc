import os
import discord
from discord.ext import commands, tasks
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
CANAL_AO_VIVO_ID = int(os.getenv("CANAL_AO_VIVO_ID", 0))
API_KEY = os.getenv("FOOTBALL_API_KEY")

intents = discord.Intents.default()
intents.message_content = True

class BotApostas(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.painel_msg = None  # Guarda a referência da mensagem fixa no canal

bot = BotApostas()

def buscar_jogos_ao_vivo():
    url = "https://free-api-live-football-data.p.rapidapi.com/football-current-live"
    headers = {
        "X-RapidAPI-Key": API_KEY,
        "X-RapidAPI-Host": "free-api-live-football-data.p.rapidapi.com"
    }
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        
        jogos = []
        inner_resp = data.get("response", {})
        matches = inner_resp.get("live", [])
        
        if not matches and isinstance(inner_resp, list):
            matches = inner_resp

        for match in matches[:8]:
            home = match.get("home", {}).get("name", "Casa")
            away = match.get("away", {}).get("name", "Fora")
            
            score = match.get("home", {}).get("score", 0)
            score_away = match.get("away", {}).get("score", 0)
            
            status_info = match.get("status", {})
            live_time = status_info.get("liveTime", {})
            tempo_str = live_time.get("short", status_info.get("scoreStr", "AO VIVO"))
            
            link_sofascore = "https://www.sofascore.com/pt"
            
            jogos.append({
                "titulo": f"⚽ {home} **{score} - {score_away}** {away}",
                "tempo": f"⏱️ `{tempo_str}`",
                "link": link_sofascore
            })
        return jogos
    except Exception as e:
        print(f"Erro detalhado ao buscar API: {e}")
        return []

@tasks.loop(minutes=2)
async def atualizar_painel_automatico():
    """Tarefa em background que atualiza o painel de 2 em 2 minutos"""
    if not CANAL_AO_VIVO_ID:
        return
        
    canal = bot.get_channel(CANAL_AO_VIVO_ID)
    if not canal:
        return

    jogos_reais = buscar_jogos_ao_vivo()
    if not jogos_reais:
        return

    embed = discord.Embed(
        title="🔴 RADAR DE APOSTAS • JOGOS EM DIRETO",
        description="Painel informativo em tempo real. Os minutos e resultados atualizam-se automaticamente:",
        color=discord.Color.red()
    )
    
    for jogo in jogos_reais:
        valor_campo = f"{jogo['tempo']} • [🔗 Abrir Sofascore]({jogo['link']})"
        embed.add_field(name=jogo['titulo'], value=valor_campo, inline=False)
    
    embed.set_footer(text="Atualização automática ativa • Via RapidAPI")

    try:
        # Se já existir uma mensagem guardada, edita-a em vez de enviar uma nova
        if bot.painel_msg:
            await bot.painel_msg.edit(embed=embed)
        else:
            # Procura nas últimas mensagens do canal se o bot já lá tem um painel para não duplicar
            async for mensagem in canal.history(limit=20):
                if mensagem.author == bot.user and mensagem.embeds:
                    bot.painel_msg = mensagem
                    await bot.painel_msg.edit(embed=embed)
                    break
            else:
                # Se não encontrar nenhuma, envia uma nova
                bot.painel_msg = await canal.send(embed=embed)
    except Exception as e:
        print(f"Erro ao atualizar painel automático: {e}")

@bot.event
async def on_ready():
    print(f"✅ Bot conectado no Kali Linux como {bot.user}")
    if not atualizar_painel_automatico.is_running():
        atualizar_painel_automatico.start()

@bot.command(name="painel_real")
@commands.has_permissions(administrator=True)
async def painel_real(ctx):
    """Força o envio imediato de um novo painel"""
    canal = bot.get_channel(CANAL_AO_VIVO_ID) or ctx.channel
    jogos_reais = buscar_jogos_ao_vivo()
    
    if not jogos_reais:
        await ctx.send("⚠️ Nenhum jogo a decorrer neste exato momento nas ligas monitoradas.")
        return

    embed = discord.Embed(
        title="🔴 RADAR DE APOSTAS • JOGOS EM DIRETO",
        description="Informação em tempo real para o canal. Consulta os jogos e abre o Sofascore abaixo:",
        color=discord.Color.red()
    )
    
    for jogo in jogos_reais:
        valor_campo = f"{jogo['tempo']} • [🔗 Abrir Sofascore]({jogo['link']})"
        embed.add_field(name=jogo['titulo'], value=valor_campo, inline=False)
    
    embed.set_footer(text="Atualizado em direto via RapidAPI • Canal informativo")
    
    bot.painel_msg = await canal.send(embed=embed)
    await ctx.message.delete()

# Comando para limpar o chat rapidamente
@bot.command(name="clear")
@commands.has_permissions(manage_messages=True)
async def clear(ctx, quantidade: int = 50):
    await ctx.message.delete()
    apagadas = await ctx.channel.purge(limit=quantidade)
    await ctx.send(f"🧹 Foram limpas **{len(apagadas)}** mensagens com sucesso!", delete_after=4)

@bot.command(name="limpar")
@commands.has_permissions(manage_messages=True)
async def limpar(ctx, quantidade: int = 50):
    await clear(ctx, quantidade)

if __name__ == "__main__":
    bot.run(TOKEN)