
import json
import re
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path

FEEDS = [
    ("IGN Brasil", "https://br.ign.com/feed.xml"),
    ("Adrenaline", "https://www.adrenaline.com.br/feed/"),
]

CATEGORIAS = [
    "Dead by Daylight",
    "Once Human",
    "Steam",
    "Atualizações",
    "Jogos grátis",
    "Promoções",
    "Lançamentos",
]


def limpar_html(texto):
    texto = re.sub(r"<[^>]+>", " ", texto or "")
    return re.sub(r"\s+", " ", unescape(texto)).strip()


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(
        c for c in texto if not unicodedata.combining(c)
    )



def classificar_noticia(titulo, resumo, link=""):
    titulo_norm = normalizar(titulo)
    resumo_norm = normalizar(resumo)
    url = normalizar(link)
    texto = f"{titulo_norm} {resumo_norm} {url}"

    # Jogos específicos: prioridade máxima.
    if any(p in texto for p in [
        "dead by daylight", "behavior interactive",
        "behaviour interactive", "the trickster",
        "the huntress", "the nurse",
    ]) or re.search(r"\bdbd\b", texto):
        return "Dead by Daylight"

    if any(p in texto for p in [
        "once human", "starry studio",
    ]):
        return "Once Human"

    # Promoções: considerar o assunto e os sinais de oferta.
    if any(p in texto for p in [
        "promocao", "promocoes", "desconto", "descontos",
        "oferta", "ofertas", "sale", "discount",
        "liquidacao", "menor preco", "preco especial",
        "por apenas", "off para membros", "cupom",
    ]):
        return "Promoções"

    # Jogos grátis.
    if any(p in texto for p in [
        "jogo gratis", "jogos gratis", "gratuito para resgatar",
        "gratuitamente", "free to keep", "free game",
        "free games", "gratis na epic", "gratis na steam",
        "resgate gratuito", "resgatar gratuitamente",
    ]):
        return "Jogos grátis"

    # Notícias realmente relacionadas à plataforma Steam.
    steam_url = (
        "store.steampowered.com" in url
        or "steamcommunity.com" in url
        or "steampowered.com" in url
    )
    steam_assunto = any(p in titulo_norm for p in [
        "steam", "steam deck", "valve", "steam next fest",
        "festival da steam",
    ])

    if steam_url or steam_assunto:
        return "Steam"

    # Lançamentos: datas, estreias e chegada de jogos.
    if any(p in texto for p in [
        "data de lancamento", "data de estreia",
        "sera lancado", "sera lancada", "chega em",
        "lancamento mundial", "novo jogo anunciado",
        "release date", "launch date", "early access",
        "acesso antecipado", "versao 1.0",
    ]):
        return "Lançamentos"

    # Atualizações: patches, temporadas e mudanças em jogos.
    if any(p in texto for p in [
        "atualizacao", "atualizacoes", "patch notes",
        "hotfix", "update", "atualizou",
        "nova temporada", "temporada estreia",
        "dlc", "expansao", "correcao de bugs",
        "notas do patch", "conteudo novo",
    ]):
        return "Atualizações"

    # Evita classificar toda notícia geral como atualização.
    # Notícias sem categoria específica ficam em "Lançamentos"
    # somente quando falam de jogos novos; as demais ficam
    # em "Atualizações" como categoria geral disponível.
    return "Atualizações"
