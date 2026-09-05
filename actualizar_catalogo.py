import json
import time
from pathlib import Path

import requests



ANILIST_URL = "https://graphql.anilist.co"

CARPETA_DATOS = Path("datos")
CARPETA_ANIMES = CARPETA_DATOS / "animes"
ARCHIVO_CONFIG = Path("config/animes.json")

CARPETA_DATOS.mkdir(exist_ok=True)
CARPETA_ANIMES.mkdir(exist_ok=True)


QUERY_BUSCAR_MEDIOS = """
query ($search: String, $page: Int) {
  Page(page: $page, perPage: 20) {
    pageInfo {
      hasNextPage
    }

    media(
      search: $search,
      type: ANIME,
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


QUERY_PERSONAJES = """
query ($mediaId: Int, $page: Int) {
  Media(id: $mediaId, type: ANIME) {

    characters(
      page: $page,
      perPage: 25,
      sort: [ROLE, RELEVANCE, ID]
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
            medium
          }

          description
          gender
          age

          dateOfBirth {
            year
            month
            day
          }

          media(type: ANIME, perPage: 10) {
            nodes {
              id

              title {
                romaji
                english
                native
              }
            }
          }
        }
      }
    }
  }
}
"""


def pedir_anilist(query, variables):
    intentos = 0

    while intentos < 8:
        intentos += 1

        try:
            respuesta = requests.post(
                ANILIST_URL,
                json={
                    "query": query,
                    "variables": variables,
                },
                timeout=30,
            )

            if respuesta.status_code == 429:
                espera = respuesta.headers.get(
                    "Retry-After"
                )

                try:
                    espera = int(espera)
                except (TypeError, ValueError):
                    espera = 12

                print(
                    f"  AniList limitó peticiones. "
                    f"Esperando {espera}s..."
                )

                time.sleep(espera)
                continue

            respuesta.raise_for_status()

            datos = respuesta.json()

            if datos.get("errors"):
                raise RuntimeError(
                    datos["errors"]
                )

            # Pequeña pausa incluso cuando funciona.
            time.sleep(1.1)

            return datos["data"]

        except requests.RequestException as error:

            if intentos >= 8:
                raise

            espera = min(
                intentos * 3,
                20,
            )

            print(
                f"  Error de red: {error}"
            )

            print(
                f"  Reintentando en {espera}s..."
            )

            time.sleep(espera)

    raise RuntimeError(
        "AniList no respondió correctamente."
    )


def normalizar(texto):
    if not texto:
        return ""

    return (
        texto
        .casefold()
        .replace("：", ":")
        .strip()
    )


def medio_coincide(medio, variantes):
    titulos = medio.get(
        "title",
        {}
    )

    valores = [
        titulos.get("romaji"),
        titulos.get("english"),
        titulos.get("native"),
    ]

    valores = [
        normalizar(valor)
        for valor in valores
        if valor
    ]

    variantes = [
        normalizar(valor)
        for valor in variantes
    ]

    for titulo in valores:
        for variante in variantes:

            if (
                variante in titulo
                or titulo in variante
            ):
                return True

    return False


def buscar_medios(datos_anime):
    encontrados = []

    for pagina in range(1, 4):

        datos = pedir_anilist(
            QUERY_BUSCAR_MEDIOS,
            {
                "search": datos_anime["busqueda"],
                "page": pagina,
            },
        )

        pagina_datos = datos["Page"]

        for medio in pagina_datos["media"]:

            if medio_coincide(
                medio,
                datos_anime["variantes"],
            ):
                encontrados.append(
                    medio
                )

        if not pagina_datos[
            "pageInfo"
        ]["hasNextPage"]:
            break

    # Eliminar medios duplicados.
    unicos = {}

    for medio in encontrados:
        unicos[medio["id"]] = medio

    return list(
        unicos.values()
    )


def prioridad_rol(rol):
    prioridades = {
        "MAIN": 3,
        "SUPPORTING": 2,
        "BACKGROUND": 1,
    }

    return prioridades.get(
        rol,
        0,
    )


def cargar_personajes(media_id):
    personajes = []

    pagina = 1

    while True:

        datos = pedir_anilist(
            QUERY_PERSONAJES,
            {
                "mediaId": media_id,
                "page": pagina,
            },
        )

        conexion = (
            datos["Media"]["characters"]
        )

        personajes.extend(
            conexion["edges"]
        )

        if not conexion[
            "pageInfo"
        ]["hasNextPage"]:
            break

        pagina += 1

        # Protección frente a datos inesperados.
        if pagina > 20:
            break

    return personajes


def actualizar_anime(clave, datos_anime):
    print()
    print("=" * 60)
    print(
        f"Actualizando: {datos_anime['nombre']}"
    )
    print("=" * 60)

    medios = buscar_medios(
        datos_anime
    )

    if not medios:
        print(
            "  No se encontraron medios."
        )
        return None

    portada = None

    for medio in medios:
        cover = medio.get(
            "coverImage"
        ) or {}

        portada = (
            cover.get("extraLarge")
            or cover.get("large")
        )

        if portada:
            break

    personajes = {}

    for numero, medio in enumerate(
        medios,
        start=1,
    ):

        titulo = (
            medio.get("title", {}).get("english")
            or medio.get("title", {}).get("romaji")
            or str(medio["id"])
        )

        print(
            f"  Medio {numero}/{len(medios)}: "
            f"{titulo}"
        )

        edges = cargar_personajes(
            medio["id"]
        )

        for edge in edges:

            nodo = edge.get(
                "node"
            ) or {}

            personaje_id = nodo.get(
                "id"
            )

            if not personaje_id:
                continue

            nuevo = {
                "id": personaje_id,

                "rol": edge.get(
                    "role"
                ),

                "nombre": nodo.get(
                    "name"
                ) or {},

                "imagen": nodo.get(
                    "image"
                ) or {},

                "descripcion": nodo.get(
                    "description"
                ),

                "genero": nodo.get(
                    "gender"
                ),

                "edad": nodo.get(
                    "age"
                ),

                "fecha_nacimiento": nodo.get(
                    "dateOfBirth"
                ) or {},

                "media": (
                    nodo.get(
                        "media"
                    ) or {}
                ).get(
                    "nodes",
                    []
                ),
            }

            anterior = personajes.get(
                personaje_id
            )

            if (
                anterior is None
                or prioridad_rol(
                    nuevo["rol"]
                )
                > prioridad_rol(
                    anterior["rol"]
                )
            ):
                personajes[
                    personaje_id
                ] = nuevo

    lista_personajes = list(
        personajes.values()
    )

    lista_personajes.sort(
        key=lambda p: (
            -prioridad_rol(
                p["rol"]
            ),
            (
                p.get(
                    "nombre"
                ) or {}
            ).get(
                "full",
                "",
            ).casefold(),
        )
    )

    resultado = {
        "clave": clave,

        "nombre": datos_anime[
            "nombre"
        ],

        "descripcion": datos_anime[
            "descripcion"
        ],

        "generos": datos_anime.get(
            "generos",
            [],
        ),

        "portada": portada,

        "medios": medios,

        "personajes": lista_personajes,

        "cantidad_personajes": len(
            lista_personajes
        ),

        "actualizado": int(
            time.time()
        ),
    }

    archivo = (
        CARPETA_ANIMES
        / f"{clave}.json"
    )

    archivo.write_text(
        json.dumps(
            resultado,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"  Guardado: {archivo}"
    )

    print(
        f"  Personajes: "
        f"{len(lista_personajes)}"
    )

    return resultado


def cargar_configuracion():
    if not ARCHIVO_CONFIG.exists():
        raise FileNotFoundError(
            f"No existe {ARCHIVO_CONFIG}"
        )

    return json.loads(
        ARCHIVO_CONFIG.read_text(
            encoding="utf-8"
        )
    )


def reconstruir_catalogo():
    catalogo = {}

    for archivo in sorted(
        CARPETA_ANIMES.glob("*.json")
    ):
        try:
            datos = json.loads(
                archivo.read_text(
                    encoding="utf-8"
                )
            )

            clave = datos.get("clave")

            if not clave:
                continue

            catalogo[clave] = {
                "clave": clave,
                "nombre": datos.get(
                    "nombre"
                ),
                "descripcion": datos.get(
                    "descripcion"
                ),
                "generos": datos.get(
                    "generos",
                    []
                ),
                "portada": datos.get(
                    "portada"
                ),
                "cantidad_personajes": datos.get(
                    "cantidad_personajes",
                    len(
                        datos.get(
                            "personajes",
                            []
                        )
                    )
                ),
            }

        except Exception as error:
            print(
                f"[CATÁLOGO] No pude leer "
                f"{archivo}: {error}"
            )

    archivo_catalogo = (
        CARPETA_DATOS
        / "catalogo.json"
    )

    archivo_catalogo.write_text(
        json.dumps(
            catalogo,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    return catalogo


def actualizar_lista(
    claves,
    configuracion,
    forzar=False
):
    total = len(claves)

    completados = 0
    omitidos = 0
    errores = []

    for numero, clave in enumerate(
        claves,
        start=1
    ):
        print()
        print(
            f"[{numero}/{total}] {clave}"
        )

        if clave not in configuracion:
            print(
                "  No existe en config/animes.json"
            )

            errores.append(clave)
            continue

        archivo = (
            CARPETA_ANIMES
            / f"{clave}.json"
        )

        if archivo.exists() and not forzar:
            print(
                "  Ya existe. Se omite."
            )

            omitidos += 1
            continue

        try:
            resultado = actualizar_anime(
                clave,
                configuracion[clave]
            )

            if resultado is None:
                errores.append(clave)
            else:
                completados += 1

            # Reconstruimos después de cada anime.
            # Así nunca perdemos progreso.
            reconstruir_catalogo()

        except KeyboardInterrupt:
            print()
            print(
                "Proceso detenido por el usuario."
            )

            reconstruir_catalogo()
            raise

        except Exception as error:
            print(
                f"  ERROR: {error}"
            )

            errores.append(clave)

            reconstruir_catalogo()

    catalogo = reconstruir_catalogo()

    print()
    print("=" * 60)
    print("ACTUALIZACIÓN TERMINADA")
    print("=" * 60)

    print(
        f"Configurados: "
        f"{len(configuracion)}"
    )

    print(
        f"Guardados actualmente: "
        f"{len(catalogo)}"
    )

    print(
        f"Descargados ahora: "
        f"{completados}"
    )

    print(
        f"Omitidos: "
        f"{omitidos}"
    )

    if errores:
        print(
            f"Errores: {len(errores)}"
        )

        for clave in errores:
            print(
                f"  - {clave}"
            )
    else:
        print(
            "Errores: 0"
        )


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Actualizador local de "
            "Anime Encyclopedia"
        )
    )

    grupo = parser.add_mutually_exclusive_group(
        required=True
    )

    grupo.add_argument(
        "--nuevos",
        action="store_true",
        help=(
            "Descarga solamente animes "
            "que todavía no existen."
        )
    )

    grupo.add_argument(
        "--todos",
        action="store_true",
        help=(
            "Actualiza todos los animes "
            "desde cero."
        )
    )

    grupo.add_argument(
        "--anime",
        type=str,
        help=(
            "Actualiza un anime concreto "
            "por su clave."
        )
    )

    args = parser.parse_args()

    configuracion = (
        cargar_configuracion()
    )

    if args.anime:
        if args.anime not in configuracion:
            raise SystemExit(
                f"Anime desconocido: "
                f"{args.anime}"
            )

        actualizar_lista(
            [args.anime],
            configuracion,
            forzar=True
        )

        return

    if args.todos:
        actualizar_lista(
            list(
                configuracion.keys()
            ),
            configuracion,
            forzar=True
        )

        return

    if args.nuevos:
        nuevos = []

        for clave in configuracion:
            archivo = (
                CARPETA_ANIMES
                / f"{clave}.json"
            )

            if not archivo.exists():
                nuevos.append(
                    clave
                )

        print(
            f"Animes pendientes: "
            f"{len(nuevos)}"
        )

        if not nuevos:
            reconstruir_catalogo()

            print(
                "No hay animes nuevos."
            )

            return

        actualizar_lista(
            nuevos,
            configuracion,
            forzar=False
        )


if __name__ == "__main__":
    main()
