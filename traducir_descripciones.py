import json
import time
from pathlib import Path

from main import traducir_con_groq


ARCHIVO = Path("config/animes.json")


def guardar(datos):
    ARCHIVO.write_text(
        json.dumps(
            datos,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main():
    datos = json.loads(
        ARCHIVO.read_text(
            encoding="utf-8"
        )
    )

    total = len(datos)

    traducidos = 0
    omitidos = 0

    for numero, (clave, anime) in enumerate(
        datos.items(),
        start=1,
    ):
        nombre = anime.get(
            "nombre",
            clave,
        )

        descripcion = anime.get(
            "descripcion",
            "",
        )

        descripcion_es = anime.get(
            "descripcion_es"
        )

        print()
        print(
            f"[{numero}/{total}] {nombre}"
        )

        if descripcion_es:
            print(
                "Ya tiene descripción en español."
            )
            omitidos += 1
            continue

        if not descripcion:
            print(
                "Sin descripción."
            )
            anime["descripcion_es"] = ""
            guardar(datos)
            omitidos += 1
            continue

        print(
            "Traduciendo al español..."
        )

        traduccion = traducir_con_groq(
            descripcion,
            "es",
        )

        if not traduccion:
            print(
                "ERROR: no se obtuvo traducción."
            )
            continue

        anime["descripcion_es"] = traduccion

        guardar(datos)

        traducidos += 1

        print(
            "Guardada."
        )

        time.sleep(0.8)

    print()
    print("=" * 60)
    print("TRADUCCIÓN TERMINADA")
    print("=" * 60)
    print(
        f"Traducidos ahora: {traducidos}"
    )
    print(
        f"Ya existentes/omitidos: {omitidos}"
    )
    print(
        f"Total configurados: {total}"
    )


if __name__ == "__main__":
    main()
