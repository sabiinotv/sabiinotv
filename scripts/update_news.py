
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
    texto = normalizar(f"{titulo} {resumo} {link}")
    url = normalizar(link)

    # Jogos específicos têm prioridade.
    if any(p in texto for p in [
        "dead by daylight", " dbd ", "behavior interactive",
        "behaviour interactive", "the trickster",
        "o mercenario", "the huntress", "the nurse",
    ]):
        return "Dead by Daylight"

    if any(p in texto for p in [
        "once human", "starry studio",
    ]):
        return "Once Human"

    # Jogos gratuitos e promoções.
    if any(p in texto for p in [
        "jogo gratis", "jogos gratis", "gratuito para resgatar",
        "gratuitamente", "free to keep", "free game",
        "free games", "gratis na epic", "gratis na steam",
        "resgate gratuito", "resgatar gratuitamente",
    ]):
        return "Jogos grátis"

    if any(p in texto for p in [
        "promocao", "promocoes", "desconto", "descontos",
        "oferta", "ofertas", "sale", "discount",
        "liquidacao", "menor preco",
    ]):
        return "Promoções"

    # Lançamentos e anúncios de novos jogos.
    if any(p in texto for p in [
        "data de lancamento", "data de estreia",
        "sera lancado", "sera lancada", "chega em",
        "lancamento mundial", "novo jogo anunciado",
        "revealed", "release date", "launch date",
    ]):
        return "Lançamentos"

    # Atualizações, patches e conteúdo novo.
    if any(p in texto for p in [
        "atualizacao", "atualizacoes", "patch notes",
        "patch", "hotfix", "update", "atualizou",
        "nova temporada", "temporada estreia",
        "dlc", "expansao", "correcao de bugs",
    ]):
        return "Atualizações"

    # Notícias diretamente relacionadas à plataforma Steam.
    if (
        "steam" in texto
        or "steampowered.com" in url
        or "store.steampowered.com" in url
    ):
        return "Steam"

    # Categoria padrão para notícias gerais de games.
    return "Atualizações"


def texto_elemento(item, nome):
    elemento = item.find(nome)
    if elemento is None:
        return ""
    return "".join(elemento.itertext()).strip()


def data_publicacao(item):
    for nome in (
        "pubDate",
        "{http://purl.org/dc/elements/1.1/}date",
    ):
        valor = texto_elemento(item, nome)
        if valor:
            try:
                data = parsedate_to_datetime(valor)
                if data.tzinfo is None:
                    data = data.replace(tzinfo=timezone.utc)
                return data.astimezone(timezone.utc).isoformat()
            except (ValueError, TypeError, OverflowError):
                try:
                    data = datetime.fromisoformat(
                        valor.replace("Z", "+00:00")
                    )
                    if data.tzinfo is None:
                        data = data.replace(tzinfo=timezone.utc)
                    return data.astimezone(timezone.utc).isoformat()
                except (ValueError, TypeError, OverflowError):
                    pass
    return ""


def buscar_feed(nome, url):
    pedido = urllib.request.Request(
        url,
        headers={"User-Agent": "SabinoTV-NewsBot/1.0"},
    )

    with urllib.request.urlopen(pedido, timeout=25) as resposta:
        xml = resposta.read()

    raiz = ET.fromstring(xml)
    encontrados = raiz.findall(".//item")

    if not encontrados:
        encontrados = raiz.findall(
            ".//{http://www.w3.org/2005/Atom}entry"
        )

    noticias = []

    for item in encontrados:
        titulo = limpar_html(texto_elemento(item, "title"))
        link = texto_elemento(item, "link")

        if not link:
            link_elemento = item.find(
                "{http://www.w3.org/2005/Atom}link"
            )
            if link_elemento is not None:
                link = link_elemento.attrib.get("href", "")

        resumo = limpar_html(
            texto_elemento(item, "description")
            or texto_elemento(item, "summary")
        )

        if titulo and link.startswith("https://"):
            categoria = classificar_noticia(
                titulo, resumo, link
            )

            noticias.append({
                "titulo": titulo,
                "resumo": resumo[:350],
                "link": link,
                "fonte": nome,
                "data": data_publicacao(item),
                "categoria": categoria,
            })

    return noticias


def main():
    noticias = []

    for nome, url in FEEDS:
        try:
            resultado = buscar_feed(nome, url)
            noticias.extend(resultado)
            print(
                f"{nome}: {len(resultado)} notícias encontradas"
            )
        except Exception as erro:
            print(f"Aviso: não foi possível buscar {nome}: {erro}")

    if not noticias:
        raise RuntimeError(
            "Nenhuma notícia foi obtida. "
            "O arquivo anterior foi preservado."
        )

    noticias.sort(key=lambda n: n["data"], reverse=True)

    unicas = []
    links_vistos = set()

    for noticia in noticias:
        if noticia["link"] not in links_vistos:
            links_vistos.add(noticia["link"])
            unicas.append(noticia)

    selecionadas = unicas[:60]

    dados = {
        "atualizado_em": datetime.now(timezone.utc).isoformat(),
        "categorias": CATEGORIAS,
        "noticias": selecionadas,
    }

    destino = Path("noticias.json")
    temporario = destino.with_suffix(".json.tmp")

    temporario.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporario.replace(destino)

    print(
        f"Arquivo noticias.json atualizado com "
        f"{len(selecionadas)} notícias."
    )

    for categoria in CATEGORIAS:
        quantidade = sum(
            n["categoria"] == categoria for n in selecionadas
        )
        print(f"{categoria}: {quantidade}")


if __name__ == "__main__":
    main()
