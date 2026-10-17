
import json
import re
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

def limpar_html(texto):
    texto = re.sub(r"<[^>]+>", " ", texto or "")
    return re.sub(r"\s+", " ", unescape(texto)).strip()

def texto_elemento(item, nome):
    elemento = item.find(nome)
    if elemento is None:
        return ""
    return "".join(elemento.itertext()).strip()

def data_publicacao(item):
    for nome in ("pubDate", "{http://purl.org/dc/elements/1.1/}date"):
        valor = texto_elemento(item, nome)
        if valor:
            try:
                data = parsedate_to_datetime(valor)
                return data.astimezone(timezone.utc).isoformat()
            except (ValueError, TypeError, OverflowError):
                try:
                    return datetime.fromisoformat(
                        valor.replace("Z", "+00:00")
                    ).astimezone(timezone.utc).isoformat()
                except (ValueError, TypeError, OverflowError):
                    pass
    return ""

def buscar_feed(nome, url):
    pedido = urllib.request.Request(
        url,
        headers={"User-Agent": "SabinoTV-NewsBot/1.0"}
    )

    with urllib.request.urlopen(pedido, timeout=25) as resposta:
        xml = resposta.read()

    raiz = ET.fromstring(xml)
    encontrados = raiz.findall(".//item")

    # Compatibilidade com feeds no formato Atom
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
            noticias.append({
                "titulo": titulo,
                "resumo": resumo[:350],
                "link": link,
                "fonte": nome,
                "data": data_publicacao(item),
            })

    return noticias

def main():
    noticias = []

    for nome, url in FEEDS:
        try:
            resultado = buscar_feed(nome, url)
            noticias.extend(resultado)
            print(f"{nome}: {len(resultado)} notícias encontradas")
        except Exception as erro:
            print(f"Aviso: não foi possível buscar {nome}: {erro}")

    # Não publicar um arquivo vazio se todas as fontes falharem.
    if not noticias:
        raise RuntimeError(
            "Nenhuma notícia foi obtida. O arquivo anterior foi preservado."
        )

    noticias.sort(key=lambda n: n["data"], reverse=True)

    # Remove links repetidos e mantém até 60 notícias.
    unicas = []
    links_vistos = set()

    for noticia in noticias:
        if noticia["link"] not in links_vistos:
            links_vistos.add(noticia["link"])
            unicas.append(noticia)

    dados = {
        "atualizado_em": datetime.now(timezone.utc).isoformat(),
        "noticias": unicas[:60],
    }

    destino = Path("noticias.json")
    temporario = destino.with_suffix(".json.tmp")
    temporario.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporario.replace(destino)

    print(f"Arquivo noticias.json atualizado com {len(dados['noticias'])} notícias.")

if __name__ == "__main__":
    main()
