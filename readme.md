# Proyecto Scraper de Imágenes

Este proyecto es un web scraper que extrae imágenes de un buscador específico utilizando Selenium y otras herramientas. A continuación, se detallan los pasos necesarios para instalar las dependencias y configurar el entorno para ejecutar el proyecto.

## Instalación

### 1. Instalar Conda

Para gestionar los entornos y dependencias, se utiliza **Conda**. Si no tienes Conda instalado, puedes descargarlo desde el siguiente enlace:

[Descargar Miniconda](https://docs.conda.io/en/latest/miniconda.html)

### 2. Crear el entorno desde el archivo `scraper.yml`

El archivo `scraper.yml` contiene las dependencias necesarias para ejecutar el proyecto. Para crear un nuevo entorno a partir de este archivo, sigue los siguientes pasos:

```bash
# Crear el entorno con el archivo scraper.yml
conda env create -f scraper.yml

# Activar el entorno
conda activate scraper
```

### 3. Instalar Google Chrome

El scraper utiliza Selenium, que requiere un navegador para funcionar. Debes instalar Google Chrome si no lo tienes ya instalado.

[Descargar Google Chrome](https://www.google.com/intl/es-419/chrome/dr/download)

### 4. Descargar Chromedriver

El Chromedriver es necesario para que Selenium pueda controlar el navegador Chrome. Asegúrate de descargar la versión del Chromedriver que coincida con la versión de Chrome instalada.

1. Para encontrar la versión de Chrome instalada, abre Chrome y escribe en la barra de búsqueda:

```bash
chrome://settings/help
```
2. Visita la página oficial de descarga de Chromedriver.

[Descargar Chromedriver](https://developer.chrome.com/docs/chromedriver/downloads)

3. Descarga la versión correcta según la versión de Chrome instalada en tu sistema.

4. Coloca el archivo descargado en la ruta correspondiente dentro del proyecto, o ajusta la variable CHROMEDRIVER_PATH en el archivo config.ini.



## Configuracion (config.ini)
El archivo config.ini contiene todas las configuraciones necesarias para ejecutar el scraper y otros aspectos del proyecto. A continuación se explica cada sección y variable del archivo:

[HTML]
Esta sección contiene configuraciones relacionadas con el parsing de los elementos HTML de la página web desde la que se están descargando las imágenes.

divTumbnailContainerID: Clase del div que contiene los thumbnails (miniaturas) de las imágenes. Se utiliza para separar los thumbnails de la página de aquellos que son resultados relacionados.
thumbnailJsname: jsname de los thumbnails. Sirve para identificar y buscar los elementos thumbnail mediante Selenium.
xpath: Ruta XPath que se usa para localizar los thumbnails en el HTML.
imgClass: Clase CSS que identifica el objeto HTML de las imágenes grandes mostradas en el buscador.
verMasClass: Clase CSS del botón "Ver Más", el cual carga más imágenes relacionadas cuando se hace clic.
endVerMasClass: Clase del botón al final de la página para cargar más resultados de imágenes.
endClass: Clase de un objeto que solo aparece al final de la página, usado para saber cuándo la página ha llegado al final.

[Files]
Esta sección contiene configuraciones relacionadas con los archivos y rutas utilizadas en el proyecto.

CHROMEDRIVER_PATH: Ruta al archivo chromedriver que Selenium utiliza para controlar el navegador Chrome.
outputPath: Ruta de salida donde se guardarán las imágenes descargadas.
csvTimeMeasure: Archivo CSV donde se guardarán las mediciones del tiempo de ejecución global.
csvThroughput: Archivo CSV donde se guarda el rendimiento (throughput) del scraper.
csvNodosArbol: Archivo CSV donde se almacenan los nodos procesados del árbol de imágenes (para control interno del scraper).
csvImagenes: Archivo CSV donde se almacenan los datos de las imágenes descargadas.

[AnomalyDetection]
Configuración relacionada con la detección de anomalías a partir de imágenes.

url: URL del servicio API de detección de anomalías al que se envían las imágenes procesadas.

[Query]
Esta sección define las consultas de búsqueda para extraer las imágenes.

query: Texto principal de la consulta.
hard_query: Palabras estrictas que deben aparecer en los resultados (as_epq en las búsquedas de Google).
soft_query: Palabras opcionales que pueden aparecer en los resultados (as_oq en las búsquedas de Google).
not_query: Palabras que no deben aparecer en los resultados (as_eq en las búsquedas de Google).
safe_search: Activar o desactivar la búsqueda segura para filtrar contenido sensible.
Nota: Puedes agregar múltiples consultas en el archivo config.ini, como Query1, Query2, etc., y estas serán cargadas automáticamente en el programa.

[General]
Esta sección contiene configuraciones generales del programa.

cantidad_productores: Cantidad de threads o productores que se utilizarán para descargar las imágenes en paralelo.
cantidadImagenes: Cantidad máxima de imágenes que el scraper debe descargar.
headless: Si está activado (True), el navegador Chrome se ejecutará en modo "headless" (sin interfaz gráfica).
trigger_tiempo: Si está activado (True), se utilizará un cronómetro para medir el tiempo de ejecución.
tiempoCronometro: Límite de tiempo en segundos para el cronómetro.
valorPoda: Umbral utilizado en los algoritmos internos del scraper para optimizar el rendimiento.

## Ejecución del Programa
Una vez que hayas configurado el entorno, descargado las dependencias, y ajustado el archivo config.ini según tus necesidades, puedes ejecutar el programa con:

```bash
python scraper.py
```

Esto activará el scraper y comenzará a descargar las imágenes según las configuraciones y queries definidas en config.ini.

## Contribuciones

Si deseas contribuir al proyecto, por favor sigue los siguientes pasos:

1. Haz un fork del repositorio.
2. Crea una rama para tu contribución (git checkout -b feature/nueva-funcionalidad).
3. Realiza tus cambios y haz un commit (git commit -am 'Agregar nueva funcionalidad').
4. Sube tu rama (git push origin feature/nueva-funcionalidad).
5. Abre un pull request para revisión.