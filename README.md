# Decretos de Reforma a la CPEUM

Este repositorio reconstruye el desarrollo legislativo de la Constitución
Política de los Estados Unidos Mexicanos (CPEUM) desde su versión original de
1917 hasta el día de hoy, donde cada decreto o cambio constitucional se refleja
como un *commit* en `git`. A partir de estos datos se genera el sitio
<https://cpeum.mx>.

## Motivación

Las leyes, en última instancia, son textos; textos organizados, vigilados y
legislados por aquellos individuos que se rigen colectivamente bajo éstas.

El software también es texto en última instancia. Es texto que se convierte en
código binario para ser ejecutado por una computadora. Los programadores de un
software particular escriben, organizan y modifican el texto que luego resultará
en una aplicación en ejecución.

En la historia del desarrollo de software se han desarrollado herramientas que
facilitan a los desarrolladores el control del ciclo de vida del software, es
decir, el fino control de los cambios realizados, su autoría, su descripción y
sus motivos. Una de estas herramientas, y la más usada hasta ahora, es [Git].

Git controla la evolución de textos en el tiempo. Y así como se puede usar para
facilitar el desarrollo de software, también se puede utilizar para llevar el
desarrollo legislativo de las leyes.

## Formato y estructura

La Constitución está almacenada en formato [reStructured Text], o simplemente
reST, un formato de texto plano que no requiere de ningún software particular
para visualizarlo o editarlo. Esto permite comparar cualquier modificación línea
a línea, entre la versión anterior y la actual, facilitando la comprensión del
cambio.

La fuente de información es la [página de la Cámara de Diputados] que registra
los decretos y cambios constitucionales desde 1917.

El repositorio se organiza de la siguiente manera:

- `CPEUM`: los artículos de la Constitución en formato `rst`, cuyo nombre de
  archivo es el número del artículo. Incluye `cpeum.rst` (la tabla de
  contenidos) y los artículos transitorios en archivos `T<NNN>.rst` (uno por
  decreto).
- `scripts`: utilidades en Python (o Bash para tareas simples) que automatizan
  la obtención, transcripción y validación de los decretos.

## Flujo de trabajo

Cada reforma constitucional se procesa como sigue:

1. Se genera el catálogo de decretos a partir de la página de la Cámara de
   Diputados `metadata/decretos.json`.
2. Se identifica el siguiente decreto del catálogo.
3. Se descarga su PDF del Diario Oficial de la Federación.
4. Se extrae el texto (con OCR si es una imagen escaneada).
5. Se verifica la transcripción y se modifican los artículos en `CPEUM/*.rst`.
6. Se crea un *commit* con el mensaje que describe el decreto, el presidente que
   lo firmó y la referencia del Diario Oficial.

## Créditos y contacto

- Mantenimiento: Víctor M. Jáquez L.
- Sitio: <https://cpeum.mx>
- Bluesky: [@cpeum.mx]

El código fuente de este sitio es abierto y está disponible en [GitHub].

[Git]: https://es.wikipedia.org/wiki/Git
[GitHub]: https://github.com/ceyusa/cpeum-decretos
[@cpeum.mx]: https://bsky.app/profile/cpeum.mx
[reStructured Text]: https://docutils.sourceforge.io/docs/ref/rst/restructuredtext.html
[página de la Cámara de Diputados]: https://www.diputados.gob.mx/LeyesBiblio/ref/cpeum_crono.htm
