#!/usr/bin/env python3
"""
Biblioteca Personal con MongoDB (pymongo)
=========================================

Aplicación de línea de comandos para administrar una biblioteca personal.
Cada libro se guarda como un DOCUMENTO JSON dentro de la colección "libros"
de MongoDB (en lugar de una fila en una tabla relacional).

Estructura de un documento:
    {
        "_id": ObjectId("..."),          # lo genera MongoDB automáticamente
        "titulo": "Cien años de soledad",
        "autor": "Gabriel García Márquez",
        "genero": "Novela",
        "leido": false,                  # true = leído, false = no leído
        "fecha_registro": ISODate("...") # lo agrega la aplicación
    }

Configuración de la conexión (en orden de prioridad):
    1. Argumentos de línea de comandos: --uri, --db, --coleccion
    2. Variables de entorno: MONGODB_URI, MONGODB_DB, MONGODB_COLLECTION
    3. Valores por defecto: mongodb://localhost:27017 / biblioteca / libros

Uso:
    python biblioteca_mongo.py
    python biblioteca_mongo.py --uri "mongodb+srv://usuario:clave@cluster0.xxxxx.mongodb.net/"
"""

import argparse
import os
import re
import sys
from datetime import datetime, timezone

try:
    from pymongo import MongoClient
    from pymongo.errors import (
        CollectionInvalid,
        ConfigurationError,
        ConnectionFailure,
        OperationFailure,
        PyMongoError,
        WriteError,
    )
except ImportError:
    sys.exit("Falta la librería pymongo. Ejecuta: pip install -r requirements.txt")


# --------------------------------------------------------------------------- #
# Constantes
# --------------------------------------------------------------------------- #
URI_POR_DEFECTO = "mongodb://localhost:27017"
BD_POR_DEFECTO = "biblioteca"
COLECCION_POR_DEFECTO = "libros"
TIMEOUT_CONEXION_MS = 5000

CAMPOS_TEXTO = ("titulo", "autor", "genero")
ETIQUETAS = {"titulo": "Título", "autor": "Autor", "genero": "Género", "leido": "Estado de lectura"}

# Esquema JSON que MongoDB aplica a cada documento de la colección.
# Si alguien intenta insertar un documento mal estructurado, MongoDB lo rechaza.
ESQUEMA_VALIDACION = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["titulo", "autor", "genero", "leido"],
        "properties": {
            "titulo": {"bsonType": "string", "minLength": 1, "description": "texto no vacío"},
            "autor": {"bsonType": "string", "minLength": 1, "description": "texto no vacío"},
            "genero": {"bsonType": "string", "minLength": 1, "description": "texto no vacío"},
            "leido": {"bsonType": "bool", "description": "true o false"},
            "fecha_registro": {"bsonType": "date"},
        },
    }
}


# --------------------------------------------------------------------------- #
# Excepciones propias
# --------------------------------------------------------------------------- #
class ErrorConexion(Exception):
    """No se pudo establecer la conexión con MongoDB."""


class DocumentoInvalido(Exception):
    """El documento no cumple la estructura esperada."""


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def ocultar_credenciales(uri: str) -> str:
    """Oculta la contraseña de la cadena de conexión antes de mostrarla."""
    return re.sub(r"//([^:@/]+):([^@]+)@", r"//\1:****@", uri)


def problemas_documento(doc: dict) -> list:
    """
    Revisa que un documento tenga la estructura esperada.
    Devuelve una lista de problemas (vacía si el documento es válido).
    """
    problemas = []
    for campo in CAMPOS_TEXTO:
        valor = doc.get(campo)
        if not isinstance(valor, str) or not valor.strip():
            problemas.append(f"'{campo}' falta o no es un texto válido")
    if not isinstance(doc.get("leido"), bool):
        problemas.append("'leido' falta o no es booleano (true/false)")
    return problemas


# --------------------------------------------------------------------------- #
# Conexión
# --------------------------------------------------------------------------- #
def conectar(uri: str) -> MongoClient:
    """Crea el cliente y comprueba que el servidor responde (ping)."""
    uri_visible = ocultar_credenciales(uri)
    try:
        cliente = MongoClient(uri, serverSelectionTimeoutMS=TIMEOUT_CONEXION_MS)
        cliente.admin.command("ping")
        return cliente
    except ConfigurationError as e:
        raise ErrorConexion(f"La cadena de conexión no es válida ({uri_visible}): {e}")
    except OperationFailure as e:
        raise ErrorConexion(f"MongoDB rechazó las credenciales o los permisos: {e}")
    except ConnectionFailure:
        raise ErrorConexion(
            f"No se pudo conectar a MongoDB en {uri_visible}.\n"
            "Revisa que el servicio esté iniciado (o que Atlas permita tu IP) y que la URI sea correcta."
        )
    except PyMongoError as e:
        raise ErrorConexion(f"Error inesperado al conectar: {e}")


# --------------------------------------------------------------------------- #
# Acceso a datos (capa de base de datos)
# --------------------------------------------------------------------------- #
class BibliotecaDB:
    """Encapsula todas las operaciones sobre la colección de libros."""

    def __init__(self, uri: str, nombre_bd: str, nombre_coleccion: str):
        self.cliente = conectar(uri)
        self.bd = self.cliente[nombre_bd]
        self._preparar_coleccion(nombre_coleccion)
        self.coleccion = self.bd[nombre_coleccion]

    def _preparar_coleccion(self, nombre: str):
        """Crea la colección con su validador (si no existe) o lo actualiza."""
        try:
            if nombre in self.bd.list_collection_names():
                self.bd.command("collMod", nombre, validator=ESQUEMA_VALIDACION, validationLevel="moderate")
            else:
                self.bd.create_collection(nombre, validator=ESQUEMA_VALIDACION)
        except (CollectionInvalid, OperationFailure):
            # Sin permisos para crear validadores: la app igual valida por su cuenta.
            pass

    @staticmethod
    def _error_escritura(e: WriteError):
        """Convierte un error de escritura en un mensaje claro."""
        if e.code == 121:  # DocumentValidationFailure
            raise DocumentoInvalido("MongoDB rechazó el documento porque no cumple el esquema de la colección.")
        raise e

    # ---- Crear ---------------------------------------------------------- #
    def agregar(self, titulo: str, autor: str, genero: str, leido: bool):
        documento = {
            "titulo": titulo.strip(),
            "autor": autor.strip(),
            "genero": genero.strip(),
            "leido": leido,
            "fecha_registro": datetime.now(timezone.utc),
        }
        problemas = problemas_documento(documento)
        if problemas:
            raise DocumentoInvalido("; ".join(problemas))
        try:
            return self.coleccion.insert_one(documento).inserted_id
        except WriteError as e:
            self._error_escritura(e)

    # ---- Leer ----------------------------------------------------------- #
    def listar(self) -> list:
        return list(self.coleccion.find().sort("titulo", 1).collation({"locale": "es", "strength": 2}))

    def buscar(self, campo: str, texto: str) -> list:
        """Búsqueda parcial e insensible a mayúsculas con un filtro $regex."""
        filtro = {campo: {"$regex": re.escape(texto), "$options": "i"}}
        return list(self.coleccion.find(filtro).sort("titulo", 1).collation({"locale": "es", "strength": 2}))

    # ---- Actualizar ----------------------------------------------------- #
    def actualizar(self, id_libro, cambios: dict) -> bool:
        for campo, valor in cambios.items():
            if campo in CAMPOS_TEXTO and (not isinstance(valor, str) or not valor.strip()):
                raise DocumentoInvalido(f"'{campo}' debe ser un texto no vacío")
            if campo == "leido" and not isinstance(valor, bool):
                raise DocumentoInvalido("'leido' debe ser true o false")
            if campo not in ETIQUETAS:
                raise DocumentoInvalido(f"Campo desconocido: '{campo}'")
        try:
            resultado = self.coleccion.update_one({"_id": id_libro}, {"$set": cambios})
        except WriteError as e:
            self._error_escritura(e)
        return resultado.matched_count == 1

    # ---- Eliminar ------------------------------------------------------- #
    def eliminar(self, id_libro) -> bool:
        return self.coleccion.delete_one({"_id": id_libro}).deleted_count == 1

    def cerrar(self):
        self.cliente.close()


# --------------------------------------------------------------------------- #
# Entrada de datos (interfaz de consola)
# --------------------------------------------------------------------------- #
def pedir_texto(mensaje: str, actual=None) -> str:
    """
    Pide un texto obligatorio. Si se pasa 'actual', presionar Enter lo conserva
    (se usa al actualizar un libro).
    """
    while True:
        entrada = input(mensaje).strip()
        if entrada:
            return entrada
        if actual is not None:
            return actual
        print("  El campo no puede estar vacío.")


def pedir_leido(actual=None) -> bool:
    """Pide el estado de lectura (s/n). Enter conserva el valor actual."""
    while True:
        entrada = input("¿Ya lo leíste? (s/n): ").strip().lower()
        if entrada in ("s", "si", "sí", "y", "1"):
            return True
        if entrada in ("n", "no", "0"):
            return False
        if not entrada and isinstance(actual, bool):
            return actual
        print("  Responde 's' (leído) o 'n' (no leído).")


def recortar(valor, ancho: int) -> str:
    texto = "—" if valor is None else str(valor)
    return texto if len(texto) <= ancho else texto[: ancho - 1] + "…"


def mostrar_libros(libros: list):
    if not libros:
        print("  (no hay libros para mostrar)")
        return
    print(f"\n{'#':>3}  {'Título':<30} {'Autor':<22} {'Género':<16} Estado")
    print("-" * 84)
    for n, libro in enumerate(libros, 1):
        leido = libro.get("leido")
        estado = "Leído" if leido is True else "No leído" if leido is False else "?"
        aviso = "  [!] documento incompleto" if problemas_documento(libro) else ""
        print(
            f"{n:>3}  {recortar(libro.get('titulo'), 30):<30} "
            f"{recortar(libro.get('autor'), 22):<22} "
            f"{recortar(libro.get('genero'), 16):<16} {estado}{aviso}"
        )
    print()


def seleccionar_libro(libros: list):
    """Muestra la lista y devuelve el libro elegido por número (o None si cancela)."""
    mostrar_libros(libros)
    while True:
        entrada = input("Número del libro (Enter para cancelar): ").strip()
        if not entrada:
            return None
        if entrada.isdigit() and 1 <= int(entrada) <= len(libros):
            return libros[int(entrada) - 1]
        print(f"  Elige un número entre 1 y {len(libros)}.")


# --------------------------------------------------------------------------- #
# Opciones del menú
# --------------------------------------------------------------------------- #
def opcion_agregar(db: BibliotecaDB):
    print("\n--- Agregar libro ---")
    titulo = pedir_texto("Título: ")
    autor = pedir_texto("Autor: ")
    genero = pedir_texto("Género: ")
    leido = pedir_leido()
    id_nuevo = db.agregar(titulo, autor, genero, leido)
    print(f"Libro agregado correctamente (id: {id_nuevo}).")


def opcion_actualizar(db: BibliotecaDB):
    print("\n--- Actualizar libro ---")
    libros = db.listar()
    if not libros:
        print("  No hay libros registrados.")
        return
    libro = seleccionar_libro(libros)
    if libro is None:
        print("Operación cancelada.")
        return

    print("Presiona Enter para conservar el valor actual de cada campo.")
    nuevos = {}
    for campo in CAMPOS_TEXTO:
        actual = libro.get(campo)
        actual = actual if isinstance(actual, str) and actual.strip() else None
        mostrado = actual if actual else "(sin valor)"
        nuevos[campo] = pedir_texto(f"{ETIQUETAS[campo]} [{mostrado}]: ", actual=actual)
    actual_leido = libro.get("leido")
    mostrado = "Leído" if actual_leido is True else "No leído" if actual_leido is False else "(sin valor)"
    print(f"Estado actual: {mostrado}")
    nuevos["leido"] = pedir_leido(actual=actual_leido)

    # Solo se envían a MongoDB los campos que realmente cambiaron ($set)
    cambios = {campo: valor for campo, valor in nuevos.items() if libro.get(campo) != valor}
    if not cambios:
        print("No se realizaron cambios.")
        return
    if db.actualizar(libro["_id"], cambios):
        print("Libro actualizado correctamente.")
    else:
        print("No se encontró el libro (¿fue eliminado desde otra sesión?).")


def opcion_eliminar(db: BibliotecaDB):
    print("\n--- Eliminar libro ---")
    libros = db.listar()
    if not libros:
        print("  No hay libros registrados.")
        return
    libro = seleccionar_libro(libros)
    if libro is None:
        print("Operación cancelada.")
        return
    confirmar = input(f"¿Seguro que deseas eliminar '{libro.get('titulo', 'sin título')}'? (s/n): ").strip().lower()
    if confirmar not in ("s", "si", "sí"):
        print("Operación cancelada.")
        return
    if db.eliminar(libro["_id"]):
        print("Libro eliminado correctamente.")
    else:
        print("No se encontró el libro (¿ya fue eliminado?).")


def opcion_listar(db: BibliotecaDB):
    print("\n--- Listado de libros ---")
    mostrar_libros(db.listar())


def opcion_buscar(db: BibliotecaDB):
    print("\n--- Buscar libros ---")
    print("Buscar por: 1) Título   2) Autor   3) Género")
    campo = {"1": "titulo", "2": "autor", "3": "genero"}.get(input("Opción: ").strip())
    if campo is None:
        print("Opción no válida.")
        return
    texto = input(f"Texto a buscar en {ETIQUETAS[campo].lower()}: ").strip()
    if not texto:
        print("Debes escribir un texto para buscar.")
        return
    resultados = db.buscar(campo, texto)
    print(f"{len(resultados)} resultado(s).")
    mostrar_libros(resultados)


# --------------------------------------------------------------------------- #
# Programa principal
# --------------------------------------------------------------------------- #
MENU = """
=== BIBLIOTECA PERSONAL (MongoDB) ===
  1. Agregar libro
  2. Actualizar libro
  3. Eliminar libro
  4. Ver listado de libros
  5. Buscar libros
  6. Salir
"""

ACCIONES = {
    "1": opcion_agregar,
    "2": opcion_actualizar,
    "3": opcion_eliminar,
    "4": opcion_listar,
    "5": opcion_buscar,
}


def ejecutar_menu(db: BibliotecaDB):
    while True:
        print(MENU)
        opcion = input("Elige una opción: ").strip()
        if opcion == "6":
            break
        accion = ACCIONES.get(opcion)
        if accion is None:
            print("Opción no válida. Elige un número del 1 al 6.")
            continue
        try:
            accion(db)
        except DocumentoInvalido as e:
            print(f"Documento inválido: {e}")
        except ConnectionFailure:
            print("Se perdió la conexión con MongoDB. Verifica el servidor e inténtalo de nuevo.")
        except PyMongoError as e:
            print(f"Error de base de datos: {e}")


def leer_argumentos():
    ap = argparse.ArgumentParser(description="Biblioteca personal con MongoDB")
    ap.add_argument("--uri", default=os.getenv("MONGODB_URI", URI_POR_DEFECTO),
                    help="Cadena de conexión (local o MongoDB Atlas)")
    ap.add_argument("--db", default=os.getenv("MONGODB_DB", BD_POR_DEFECTO), help="Nombre de la base de datos")
    ap.add_argument("--coleccion", default=os.getenv("MONGODB_COLLECTION", COLECCION_POR_DEFECTO),
                    help="Nombre de la colección")
    return ap.parse_args()


def main():
    args = leer_argumentos()
    print(f"Conectando a {ocultar_credenciales(args.uri)} ...")
    try:
        db = BibliotecaDB(args.uri, args.db, args.coleccion)
    except ErrorConexion as e:
        sys.exit(f"Error de conexión: {e}")
    print(f"Conexión exitosa. Base de datos: '{args.db}', colección: '{args.coleccion}'.")

    try:
        ejecutar_menu(db)
    except (KeyboardInterrupt, EOFError):
        print()
    finally:
        db.cerrar()
        print("Hasta luego.")


if __name__ == "__main__":
    main()
