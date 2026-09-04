import html
import os
import re
import time

import requests
from dotenv import load_dotenv
from flask import Flask, render_template, request
from groq import Groq


# =========================================================
# CONFIGURACIÓN
# =========================================================

load_dotenv(".env")

app = Flask(__name__)

API_URL = "https://graphql.anilist.co"

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError(
        "No se encontró GROQ_API_KEY en el archivo .env"
    )

groq_client = Groq(
    api_key=GROQ_API_KEY
)


IDIOMAS = {
    "es": "Español",
    "en": "English",
    "ja": "日本語",
    "fr": "Français",
}

NOMBRES_IDIOMAS = {
    "es": "español",
    "en": "inglés",
    "ja": "japonés",
    "fr": "francés",
}


# =========================================================
# ANIMES DISPONIBLES
# =========================================================

FRANQUICIAS = {
    "rezero": {
        "nombre": "Re:Zero",
        "descripcion": "Starting Life in Another World",
        "busqueda": "Re:ZERO",
        "generos": ["Isekai", "Fantasía", "Drama"],
        "variantes": [
            "re:zero",
            "re: zero",
            "rezero",
            "re zero",
            "re：ゼロ",
            "リゼロ",
        ],
    },

    "jujutsu-kaisen": {
        "nombre": "Jujutsu Kaisen",
        "descripcion": "Hechicería, maldiciones y combates",
        "busqueda": "Jujutsu Kaisen",
        "generos": ["Acción", "Sobrenatural"],
        "variantes": [
            "jujutsu kaisen",
            "呪術廻戦",
        ],
    },

    "attack-on-titan": {
        "nombre": "Attack on Titan",
        "descripcion": "Shingeki no Kyojin",
        "busqueda": "Attack on Titan",
        "generos": ["Acción", "Drama"],
        "variantes": [
            "attack on titan",
            "shingeki no kyojin",
            "進撃の巨人",
        ],
    },

    "mushoku-tensei": {
        "nombre": "Mushoku Tensei",
        "descripcion": "Jobless Reincarnation",
        "busqueda": "Mushoku Tensei",
        "generos": ["Isekai", "Fantasía"],
        "variantes": [
            "mushoku tensei",
            "無職転生",
        ],
    },

    "gachiakuta": {
        "nombre": "Gachiakuta",
        "descripcion": "El mundo de Rudo y los Cleaners",
        "busqueda": "Gachiakuta",
        "generos": ["Acción", "Fantasía"],
        "variantes": [
            "gachiakuta",
            "ガチアクタ",
        ],
    },

    "hells-paradise": {
        "nombre": "Hell's Paradise",
        "descripcion": "Jigokuraku",
        "busqueda": "Jigokuraku",
        "generos": ["Acción", "Fantasía", "Sobrenatural"],
        "variantes": [
            "jigokuraku",
            "hell's paradise",
            "hells paradise",
            "地獄楽",
        ],
    },

    "spy-family": {
        "nombre": "SPY×FAMILY",
        "descripcion": "La familia Forger",
        "busqueda": "SPY x FAMILY",
        "generos": ["Comedia", "Acción"],
        "variantes": [
            "spy x family",
            "spy×family",
            "spy family",
            "スパイファミリー",
        ],
    },

    "kimetsu": {
        "nombre": "Kimetsu no Yaiba",
        "descripcion": "Demon Slayer",
        "busqueda": "Kimetsu no Yaiba",
        "generos": ["Acción", "Fantasía", "Sobrenatural"],
        "variantes": [
            "kimetsu no yaiba",
            "demon slayer",
            "鬼滅の刃",
        ],
    },

    "mashle": {
        "nombre": "MASHLE",
        "descripcion": "Magic and Muscles",
        "busqueda": "Mashle",
        "generos": ["Comedia", "Acción", "Fantasía"],
        "variantes": [
            "mashle",
            "マッシュル",
        ],
    },

    "my-dress-up-darling": {
        "nombre": "My Dress-Up Darling",
        "descripcion": "Sono Bisque Doll wa Koi wo Suru",
        "busqueda": "Sono Bisque Doll wa Koi wo Suru",
        "generos": ["Romance", "Comedia"],
        "variantes": [
            "sono bisque doll wa koi wo suru",
            "my dress-up darling",
            "my dress up darling",
            "その着せ替え人形は恋をする",
        ],
    },
}

cache_franquicias = {}

CACHE_DURACION = 3600


# =========================================================
# QUERIES GRAPHQL
# =========================================================

QUERY_PERSONAJE = """
query ($search: String) {
  Character(search: $search) {
    id

    name {
      full
      native
    }

    image {
      large
    }

    description(asHtml: false)

    gender
    age

    dateOfBirth {
      year
      month
      day
    }

    media(perPage: 25) {
      nodes {
        title {
          romaji
          english
        }

        type
      }
    }
  }
}
"""


QUERY_PERSONAJE_ID = """
query ($id: Int) {
  Character(id: $id) {
    id

    name {
      full
      native
    }

    image {
      large
    }

    description(asHtml: false)

    gender
    age

    dateOfBirth {
      year
      month
      day
    }

    media(perPage: 25) {
      nodes {
        title {
          romaji
          english
        }

        type
      }
    }
  }
}
"""


QUERY_MEDIOS = """
query ($search: String!, $page: Int!) {
  Page(
    page: $page
    perPage: 25
  ) {
    pageInfo {
      hasNextPage
    }

    media(
      search: $search
      type: ANIME
      sort: POPULARITY_DESC
    ) {
      id

      title {
        romaji
        english
        native
      }

      coverImage {
        extraLarge
        large
      }
    }
  }
}
"""


QUERY_PERSONAJES_MEDIO = """
query ($id: Int!, $page: Int!) {
  Media(
    id: $id
    type: ANIME
  ) {
    characters(
      page: $page
      perPage: 25
    ) {
      pageInfo {
        hasNextPage
      }

      edges {
        role

        node {
          id

          name {
            full
            native
          }

          image {
            large
          }
        }
      }
    }
  }
}
"""


# =========================================================
# ANILIST
# =========================================================

def consultar_anilist(query, variables):
    respuesta = requests.post(
        API_URL,
        json={
            "query": query,
            "variables": variables,
        },
        timeout=25,
    )

    respuesta.raise_for_status()

    datos = respuesta.json()

    if datos.get("errors"):
        print("[ERROR GRAPHQL]")
        print(datos["errors"])
        return None

    return datos.get("data")


def buscar_personaje(nombre):
    datos = consultar_anilist(
        QUERY_PERSONAJE,
        {
            "search": nombre,
        },
    )

    if not datos:
        return None

    return datos.get("Character")


def obtener_personaje_por_id(personaje_id):
    datos = consultar_anilist(
        QUERY_PERSONAJE_ID,
        {
            "id": personaje_id,
        },
    )

    if not datos:
        return None

    return datos.get("Character")


# =========================================================
# OBTENER FRANQUICIAS
# =========================================================

def coincide_franquicia(
    titulo,
    variantes,
):
    texto = " ".join([
        titulo.get("romaji") or "",
        titulo.get("english") or "",
        titulo.get("native") or "",
    ]).lower()

    return any(
        variante.lower() in texto
        for variante in variantes
    )


def obtener_medios_franquicia(clave):
    configuracion = FRANQUICIAS[clave]

    encontrados = {}

    pagina = 1

    while pagina <= 3:
        datos = consultar_anilist(
            QUERY_MEDIOS,
            {
                "search": configuracion["busqueda"],
                "page": pagina,
            },
        )

        if not datos:
            break

        pagina_datos = datos.get(
            "Page",
            {},
        )

        for medio in pagina_datos.get(
            "media",
            [],
        ):
            titulo = medio.get(
                "title",
                {},
            )

            if coincide_franquicia(
                titulo,
                configuracion["variantes"],
            ):
                encontrados[
                    medio["id"]
                ] = medio

        if not pagina_datos.get(
            "pageInfo",
            {},
        ).get("hasNextPage"):
            break

        pagina += 1

    return list(
        encontrados.values()
    )


def obtener_portadas_animes():
    portadas = {}

    for clave in FRANQUICIAS:
        try:
            medios = obtener_medios_franquicia(
                clave
            )

            if not medios:
                portadas[clave] = None
                continue

            # Como AniList ordena por popularidad,
            # usamos la primera obra encontrada
            # como portada principal de la franquicia.
            medio_principal = medios[0]

            portada = medio_principal.get(
                "coverImage",
                {},
            )

            portadas[clave] = (
                portada.get("extraLarge")
                or portada.get("large")
            )

        except Exception as error:
            print(
                f"[PORTADA {clave}] {error}"
            )

            portadas[clave] = None

    return portadas


def prioridad_rol(rol):
    prioridades = {
        "MAIN": 0,
        "SUPPORTING": 1,
        "BACKGROUND": 2,
    }

    return prioridades.get(
        rol,
        3,
    )


def obtener_personajes_medio(media_id):
    personajes = []

    pagina = 1

    while pagina <= 12:
        datos = consultar_anilist(
            QUERY_PERSONAJES_MEDIO,
            {
                "id": media_id,
                "page": pagina,
            },
        )

        if not datos:
            break

        media = datos.get("Media")

        if not media:
            break

        conexion = media.get(
            "characters",
            {},
        )

        personajes.extend(
            conexion.get(
                "edges",
                [],
            )
        )

        if not conexion.get(
            "pageInfo",
            {},
        ).get("hasNextPage"):
            break

        pagina += 1

    return personajes


def cargar_franquicia(
    clave,
    forzar=False,
):
    ahora = time.time()

    cache = cache_franquicias.get(
        clave
    )

    if (
        cache
        and cache.get("personajes")
        and not forzar
        and ahora - cache.get(
            "actualizado",
            0,
        ) < CACHE_DURACION
    ):
        return cache["personajes"]

    configuracion = FRANQUICIAS[clave]

    nombre = configuracion["nombre"]

    print()
    print(
        f"[{nombre}] "
        "Buscando obras de la franquicia..."
    )

    medios = obtener_medios_franquicia(
        clave
    )

    print(
        f"[{nombre}] "
        f"Obras encontradas: {len(medios)}"
    )

    personajes_unicos = {}

    for numero, medio in enumerate(
        medios,
        start=1,
    ):
        titulo = (
            medio.get(
                "title",
                {},
            ).get("english")
            or
            medio.get(
                "title",
                {},
            ).get("romaji")
            or
            "Sin título"
        )

        print(
            f"[{nombre}] "
            f"{numero}/{len(medios)} "
            f"{titulo}"
        )

        try:
            personajes = (
                obtener_personajes_medio(
                    medio["id"]
                )
            )

        except requests.RequestException as error:
            print(
                f"[ERROR] {titulo}: {error}"
            )

            continue

        for edge in personajes:
            nodo = edge.get("node")

            if not nodo:
                continue

            personaje_id = nodo.get("id")

            if personaje_id is None:
                continue

            rol = (
                edge.get("role")
                or "BACKGROUND"
            )

            nuevo = {
                "id": personaje_id,

                "name": nodo.get(
                    "name",
                    {},
                ),

                "image": nodo.get(
                    "image",
                    {},
                ),

                "role": rol,
            }

            if personaje_id not in personajes_unicos:
                personajes_unicos[
                    personaje_id
                ] = nuevo

            else:
                anterior = personajes_unicos[
                    personaje_id
                ]

                if (
                    prioridad_rol(rol)
                    <
                    prioridad_rol(
                        anterior.get("role")
                    )
                ):
                    anterior["role"] = rol

    lista = list(
        personajes_unicos.values()
    )

    lista.sort(
        key=lambda personaje: (
            prioridad_rol(
                personaje.get("role")
            ),

            (
                personaje
                .get("name", {})
                .get("full")
                or ""
            ).lower(),
        )
    )

    cache_franquicias[clave] = {
        "personajes": lista,
        "actualizado": ahora,
    }

    print(
        f"[{nombre}] "
        f"Personajes únicos: {len(lista)}"
    )

    print()

    return lista


# =========================================================
# LIMPIAR TEXTO ANILIST
# =========================================================

def limpiar_texto_anilist(texto):
    if not texto:
        return texto

    texto = html.unescape(texto)

    reemplazos = {
        "Sin Archbishop":
            "Arzobispo del Pecado",

        "Sin Archbishops":
            "Arzobispos del Pecado",

        "Witch Cult":
            "Culto de la Bruja",
    }

    for original, corregido in reemplazos.items():
        texto = re.sub(
            re.escape(original),
            corregido,
            texto,
            flags=re.IGNORECASE,
        )

    # [Nombre](https://...) -> Nombre
    texto = re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        r"\1",
        texto,
    )

    # Spoilers de AniList
    texto = texto.replace(
        "~~!",
        "",
    )

    texto = texto.replace(
        "!~~",
        "",
    )

    texto = texto.replace(
        "~!",
        "",
    )

    texto = texto.replace(
        "!~",
        "",
    )

    # URLs restantes
    texto = re.sub(
        r"https?://\S+",
        "",
        texto,
    )

    # HTML restante
    texto = re.sub(
        r"<[^>]+>",
        "",
        texto,
    )

    # Markdown
    texto = texto.replace(
        "\\",
        "",
    )

    texto = texto.replace(
        "**",
        "",
    )

    texto = texto.replace(
        "__",
        "",
    )

    texto = texto.replace(
        "~~",
        "",
    )

    # Espacios
    texto = re.sub(
        r"[ \t]+",
        " ",
        texto,
    )

    texto = re.sub(
        r" *\n *",
        "\n",
        texto,
    )

    texto = re.sub(
        r"\n{3,}",
        "\n\n",
        texto,
    )

    return texto.strip()


# =========================================================
# TRADUCCIÓN
# =========================================================

def traducir_con_groq(
    texto,
    idioma,
):
    if not texto:
        return texto

    texto = limpiar_texto_anilist(
        texto
    )

    idioma_destino = (
        NOMBRES_IDIOMAS.get(
            idioma,
            "español",
        )
    )

    try:
        respuesta = (
            groq_client
            .chat
            .completions
            .create(
                model="openai/gpt-oss-20b",

                messages=[
                    {
                        "role": "system",

                        "content": (
                            "Eres un traductor profesional "
                            "especializado en anime. "
                            "Traduce de forma natural y "
                            "gramaticalmente correcta. "
                            "Usa el contexto del anime "
                            "para interpretar términos. "
                            "No traduzcas palabra por palabra "
                            "si eso genera frases incorrectas. "
                            "No resumas. "
                            "No inventes información. "
                            "No añadas explicaciones. "
                            "Conserva los nombres propios. "
                            "Para Re:Zero, "
                            "'Sin Archbishop' significa "
                            "'Arzobispo del Pecado' y "
                            "'Witch Cult' significa "
                            "'Culto de la Bruja'. "
                            "Devuelve únicamente "
                            "la traducción final."
                        ),
                    },

                    {
                        "role": "user",

                        "content": (
                            f"Idioma de destino: "
                            f"{idioma_destino}\n\n"
                            f"{texto}"
                        ),
                    },
                ],

                temperature=0.1,

                max_completion_tokens=2000,

                reasoning_effort="low",

                include_reasoning=False,
            )
        )

        contenido = (
            respuesta
            .choices[0]
            .message
            .content
        )

        if not contenido:
            return texto

        return limpiar_texto_anilist(
            contenido.strip()
        )

    except Exception as error:
        print(
            f"[ERROR GROQ] {error}"
        )

        return texto


def traducir_genero(
    genero,
    idioma,
):
    traducciones = {
        "Male": {
            "es": "Masculino",
            "en": "Male",
            "ja": "男性",
            "fr": "Masculin",
        },

        "Female": {
            "es": "Femenino",
            "en": "Female",
            "ja": "女性",
            "fr": "Féminin",
        },

        "Non-binary": {
            "es": "No binario",
            "en": "Non-binary",
            "ja": "ノンバイナリー",
            "fr": "Non-binaire",
        },
    }

    if not genero:
        vacio = {
            "es": "No especificado",
            "en": "Not specified",
            "ja": "指定なし",
            "fr": "Non spécifié",
        }

        return vacio.get(
            idioma,
            "No especificado",
        )

    return (
        traducciones
        .get(genero, {})
        .get(idioma, genero)
    )


def preparar_personaje(
    personaje,
    idioma,
):
    if not personaje:
        return None

    descripcion = personaje.get(
        "description"
    )

    if descripcion:
        personaje[
            "description"
        ] = traducir_con_groq(
            descripcion,
            idioma,
        )

    personaje[
        "gender_traducido"
    ] = traducir_genero(
        personaje.get("gender"),
        idioma,
    )

    return personaje


# =========================================================
# PORTADA
# =========================================================

@app.route("/")
def inicio():
    idioma = request.args.get(
        "idioma",
        "es",
    )

    if idioma not in IDIOMAS:
        idioma = "es"

    portadas = obtener_portadas_animes()

    return render_template(
        "index.html",

        vista="inicio",

        franquicias=FRANQUICIAS,

        portadas=portadas,

        idiomas=IDIOMAS,

        idioma=idioma,

        error=None,
    )


# =========================================================
# ANIME SELECCIONADO
# =========================================================

@app.route("/anime/<clave>")
def ver_anime(clave):
    if clave not in FRANQUICIAS:
        return (
            "Anime no encontrado.",
            404,
        )

    idioma = request.args.get(
        "idioma",
        "es",
    )

    if idioma not in IDIOMAS:
        idioma = "es"

    pagina = request.args.get(
        "pagina",
        default=1,
        type=int,
    )

    if pagina < 1:
        pagina = 1

    try:
        personajes = cargar_franquicia(
            clave
        )

        error = None

    except Exception as error_anilist:
        print(
            "[ERROR FRANQUICIA] "
            f"{error_anilist}"
        )

        personajes = []

        error = (
            "No se pudieron cargar "
            "los personajes."
        )

    por_pagina = 40

    total_personajes = len(
        personajes
    )

    total_paginas = max(
        1,
        (
            total_personajes
            + por_pagina
            - 1
        ) // por_pagina,
    )

    if pagina > total_paginas:
        pagina = total_paginas

    inicio_pagina = (
        pagina - 1
    ) * por_pagina

    fin_pagina = (
        inicio_pagina
        + por_pagina
    )

    personajes_pagina = personajes[
        inicio_pagina:fin_pagina
    ]

    return render_template(
        "index.html",

        vista="anime",

        franquicias=FRANQUICIAS,

        anime=FRANQUICIAS[clave],

        clave=clave,

        personajes=personajes_pagina,

        total_personajes=total_personajes,

        pagina=pagina,

        total_paginas=total_paginas,

        idiomas=IDIOMAS,

        idioma=idioma,

        error=error,
    )


# =========================================================
# FICHA DE PERSONAJE
# =========================================================

@app.route("/personaje/<int:personaje_id>")
def ver_personaje(personaje_id):
    idioma = request.args.get(
        "idioma",
        "es",
    )

    clave = request.args.get(
        "anime",
        "",
    )

    if idioma not in IDIOMAS:
        idioma = "es"

    anime = None

    if clave in FRANQUICIAS:
        anime = FRANQUICIAS[clave]

    personaje = None
    error = None

    try:
        personaje = obtener_personaje_por_id(
            personaje_id
        )

        personaje = preparar_personaje(
            personaje,
            idioma,
        )

        if not personaje:
            error = (
                "No se encontró "
                "ese personaje."
            )

    except requests.RequestException as error_anilist:
        print(
            "[ERROR ANILIST] "
            f"{error_anilist}"
        )

        error = (
            "No se pudo conectar "
            "con AniList."
        )

    return render_template(
        "index.html",

        vista="personaje",

        personaje=personaje,

        anime=anime,

        clave=clave,

        franquicias=FRANQUICIAS,

        idiomas=IDIOMAS,

        idioma=idioma,

        error=error,
    )


# =========================================================
# BUSCADOR GLOBAL
# =========================================================

@app.route(
    "/buscar",
    methods=["POST"],
)
def buscar():
    nombre = request.form.get(
        "busqueda",
        "",
    ).strip()

    idioma = request.form.get(
        "idioma",
        "es",
    )

    clave = request.form.get(
        "anime",
        "",
    )

    if idioma not in IDIOMAS:
        idioma = "es"

    anime = None

    if clave in FRANQUICIAS:
        anime = FRANQUICIAS[clave]

    personaje = None
    error = None

    if not nombre:
        error = (
            "Escribe el nombre "
            "de un personaje."
        )

    else:
        try:
            personaje = buscar_personaje(
                nombre
            )

            personaje = preparar_personaje(
                personaje,
                idioma,
            )

            if not personaje:
                error = (
                    "No se encontró "
                    "ese personaje."
                )

        except requests.RequestException as error_anilist:
            print(
                "[ERROR ANILIST] "
                f"{error_anilist}"
            )

            error = (
                "No se pudo conectar "
                "con AniList."
            )

    return render_template(
        "index.html",

        vista="personaje",

        personaje=personaje,

        anime=anime,

        clave=clave,

        franquicias=FRANQUICIAS,

        idiomas=IDIOMAS,

        idioma=idioma,

        error=error,
    )


# =========================================================
# EJECUCIÓN
# =========================================================

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
    )
