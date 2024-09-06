from queue import Queue
from selenium import webdriver
import chromedriver_autoinstaller
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
import requests
from requests import RequestException
import threading
from threading import Thread
from selenium.common.exceptions import TimeoutException
import hashlib
import magic
import os
import time
import csv
import logging
import configparser

logger = None

class Query():  
    def __init__(self, query, hard_query="", soft_query="", not_query="", safe_search="off"):
        self.query = query
        self.hard_query = hard_query #Contienen estrictamente estas palabras (as_epq). Matchean todas
        self.soft_query = soft_query #Puede contener algunas de estas palabras (as_oq). Matchea una o más de una
        self.not_query=not_query #No contiene ninguna de estas palabras (as_eq)
        if safe_search == 'on': #Busqueda segura. Esconde todo el material sensible
            self.safe_search = 'on'
        else:
            self.safe_search = 'off'
        self.url = 'https://www.google.com/search?tbm=isch&as_epq='+self.hard_query.replace(' ', '+')+'&as_oq='+self.soft_query.replace(' ', '+')+'&as_eq='+self.not_query.replace(' ', '+')+'&safe_search='+self.safe_search.replace(' ', '+')+'&q='+self.query.replace(' ', '+')
    
    def getInitialQuery(self):
        return self.query
    
    def getHardQuery(self):
        return self.hard_query

    def getSoftQuery(self):
        return self.soft_query
    
    def getNotQuery(self):
        return self.not_query
    
    def getSafeSearch(self):
        return self.safe_search

    def getUrl(self):
        return self.url
    
    def to_string(self):
        return '[' + self.query + ',' + self.hard_query + ',' + self.soft_query + ',' + self.not_query + ',' + self.safe_search + ']'


class Config:
    HTML = {}
    Files = {}
    AnomalyDetection = {}
    Queries = list()
    General = {}

    @classmethod
    def load_config(cls, file_path='config.ini'):
        # Crear un objeto ConfigParser
        config = configparser.ConfigParser()

        # Leer el archivo config.ini
        config.read(file_path)

        # Asignar los valores a las variables estáticas
        cls.HTML = {
            'xpath': "//div[@class='"+config.get('HTML', 'divTumbnailContainerID').strip('"')+"']//div[@jsname='"+config.get('HTML', 'thumbnailJsname').strip('"')+"']",
            'imgClass': config.get('HTML', 'imgClass').strip('"'),
            'verMasClass': config.get('HTML', 'verMasClass').strip('"'),
            'endVerMasClass': config.get('HTML', 'endVerMasClass').strip('"'),
            'endClass': config.get('HTML', 'endClass').strip('"'),
        }

        cls.Files = {
            'CHROMEDRIVER_PATH': config.get('Files', 'CHROMEDRIVER_PATH').strip('"'),
            'outputPath': config.get('Files', 'outputPath').strip('"'),
            'csvTimeMeasure': config.get('Files', 'csvTimeMeasure').strip('"'),
            'csvThroughput': config.get('Files', 'csvThroughput').strip('"'),
            'csvNodosArbol': config.get('Files', 'csvNodosArbol').strip('"'),
            'csvImagenes': config.get('Files', 'csvImagenes').strip('"'),
        }

        cls.AnomalyDetection = {
            'url': config.get('AnomalyDetection', 'url').strip('"'),
        }

        cls.General = {
            'cantidad_productores': config.getint('General', 'cantidad_productores'),
            'cantidad_consumidores': config.getint('General', 'cantidad_consumidores'),
            'cantidad_distance_calculators': config.getint('General', 'cantidad_distance_calculators'),
            'cantidadImagenes': config.getint('General', 'cantidadImagenes'),
            'headless': config.getboolean('General', 'headless'),
            'trigger_tiempo': config.getboolean('General', 'trigger_tiempo'),
            'tiempoCronometro': config.getint('General', 'tiempoCronometro'),
            'valorPoda': config.getfloat('General', 'valorPoda'),
            'trigger_medidas_tiempo': config.getboolean('General', 'trigger_medidas_tiempo'),
        }

        cls.Queries = list()

        # Cargar dinámicamente las queries
        for section in config.sections():
            if section.startswith('Query'):
                print(config.get(section, 'query').strip('"'))
                query = Query(config.get(section, 'query').strip('"'), config.get(section, 'hard_query').strip('"'), 
                            config.get(section, 'soft_query').strip('"'), config.get(section, 'not_query').strip('"'), 
                            config.get(section, 'safe_search'))
                print(query.getUrl())
                cls.Queries.append(query)


class Estado():
    SIN_ASIGNAR = -1
    ASIGNADO = 0
    FINALIZADO = 1


class Node():
    def __init__(self, query = None, url = None, imgLink=None, padre=None, nivel = 0, extension = None):
        self.query = query #Es de tipo Query y representa la query inicial
        self.imgLink = imgLink #Imagen de este nodo (Si es el nodo raiz entonces es None)
        self.url = url #El link de la pagina en donde me muestran imagenes relacionadas a la imagen asociada. Seria el href del "ver mas"
        self.nivel = nivel #Nivel del nodo en el arbol
        self.extension = extension
        self.distance = None
        self.path = None #Path en donde se encuentra descargada la imagen
        self.padre = padre #Nodo padre
        
        self.nodosHijos = list() #Lista de referencias a nodos hijos
        self.estado = Estado.SIN_ASIGNAR # Estado del arbol
        
        # ---- Parametros en caso de que se extienda el nodo ---- #
        self.cantidadRecorridos = 0 #Cantidad de imagenes relacionadas recorridas
        #Cantidad de imagenes perdidas a la hora de producir
        self.cantidadTimeOut = 0
        self.cantidadRepetidos = 0
        #Cantidad de imagenes perdidas a la hora de consumir
        self.cantidadDownloadFails = 0
        #Cantidad de imagenes perdidas a la hora de calcular la distancia
        self.cantidadSvddFails = 0
        #Cantidad de imagenes podadas
        self.cantidadPodados = 0

        #Locker para evitar el race condition en las variables de cantidad de fallos. 
        #Creo que es mejor tener un solo lock para todas las variables ya que no es algo que pase muy seguido
        # y si bien se podria tener un lock para cada variable, creo que el costo en la prolijidad del codigo no vale la pena
        self.locker = threading.Lock()


    def getQuery(self):
        return self.query
    
    def setQuery(self, query):
        self.query = query

    def getImageLink(self):
        return self.imgLink

    def setImageLink(self, imgLink):
        self.imgLink = imgLink

    def getUrl(self):
        return self.url
    
    def setUrl(self, url):
        self.url = url

    def getNivel(self):
        return self.nivel
    
    def setNivel(self, nivel):
        self.nivel = nivel

    def getExtension(self):
        return self.extension
    
    def setExtension(self, extension):
        self.extension = extension

    def getDistance(self):
        return self.distance
    
    def setDistance(self, distance):
        self.distance = distance

    def getPath(self):
        return self.path
    
    def setPath(self, path):
        self.path = path

    def getPadre(self):
        return self.padre
    
    def setPadre(self, padre):
        self.padre = padre

    #Los metodos de manejo de la lista pueden variar o agregarse mas
    def addHijo(self, node):
        self.nodosHijos.append(node)
    
    def getHijos(self):
        return self.nodosHijos

    def getCantHijos(self):
        return len(self.nodosHijos)
    
    def getEstado(self):
        return self.estado
    
    def setEstado(self, estado):
        self.estado = estado

    def getCantidadRecorridos(self):
        return self.cantidadRecorridos
    
    def addCantidadRecorridos(self, suma):
        #No necesito locker porque un nodo va a estar en un solo producer
        self.cantidadRecorridos += suma

    def setCantidadRecorridos(self, cantidad):
        self.cantidadRecorridos = cantidad

    def getCantidadRepetidos(self):
        return self.cantidadRepetidos
    
    def addCantidadRepetidos(self, suma):
        with self.locker:
            self.cantidadRepetidos += suma

    def setCantidadRepetidos(self, cantidad):
        self.cantidadRepetidos = cantidad

    def getCantidadTimeouts(self):
        return self.cantidadTimeOut
    
    def addCantidadTimeouts(self, suma):
        with self.locker:
            self.cantidadTimeOut += suma
    
    def setCantidadTimeouts(self, cantidad):
        self.cantidadTimeOut = cantidad
    
    def getCantidadDownloadFails(self):
        return self.cantidadDownloadFails
    
    def addCantidadDownloadFails(self, suma):
        with self.locker:
            self.cantidadDownloadFails += suma
    
    def setCantidadDownloadFails(self, cantidad):
        self.cantidadDownloadFails = cantidad

    def getCantidadSvddFails(self):
        return self.cantidadSvddFails
    
    def addCantidadSvddFails(self, suma):
        with self.locker:
            self.cantidadSvddFails += suma
    
    def setCantidadSvddFails(self, cantidad):
        self.cantidadSvddFails = cantidad

    def getCantidadPodados(self):
        return self.cantidadPodados
    
    def addCantidadPodados(self, suma):
        with self.locker:
            self.cantidadPodados += suma
    
    def setCantidadPodados(self, cantidad):
        self.cantidadPodados = cantidad

    def getImgExitosas(self):
        return self.cantidadRecorridos - self.cantidadDownloadFails - self.cantidadRepetidos - self.cantidadTimeOut - self.cantidadSvddFails - self.cantidadPodados
    
    #Retorna la referencia del nodo el cual es el link de la imagen hasheado o la query en caso de ser raiz
    def getReferencia(self): 
        if(self.nivel == 0):
            return self.query.to_string()
        else:
            return hashlib.md5(self.imgLink.encode()).hexdigest()
        

class Producer(threading.Thread):
    def __init__(self, manager, name=None, waitLoadTimeOut = 3, headless = True):
        Thread.__init__(self,name=name)
        self.manager = manager
        self.waitLoadTimeOut = waitLoadTimeOut #Tiempo que espera para que se cargue la imagen
        self.stopper = False #Trigger que apaga al producer
        self.headless = headless

    def apagar(self):
        print(self.name + ": SE TRIGGEREO EL STOP DEL PRODUCTOR")
        self.stopper = True

    def run(self):
        print("PRODUCTOR CON NOMBRE: " + self.name + ", COMIENZA CON CODIGO: " + str(threading.get_native_id()))
        op = webdriver.ChromeOptions()
        if self.headless:
            op.add_argument('--headless')
            op.add_argument('--disable-gpu')  # Necesario para headless en algunas versiones de Linux
            op.add_argument('--no-sandbox')   # Necesario para headless en algunas versiones de Linux
            op.add_argument('--disable-dev-shm-usage')  # Necesario para headless en algunas versiones de Linux
        service = ChromeService(executable_path=Config.Files['CHROMEDRIVER_PATH'])
        driver = webdriver.Chrome(service=service, options=op)

        while not self.stopper:
            print(self.name+": tratando de obtener nodo")
            nodoActual = self.manager.getNodoProducer()
            if nodoActual == None:
                print(self.name+": Se obtuvo NONE en la queue")
                continue
            print(self.name+": NUEVO NODO obtenido")

            url = nodoActual.getUrl()
            driver.get(url)
            nodoActual.setEstado(Estado.ASIGNADO)
            self.iterate(driver=driver, nodoActual=nodoActual)

            #Una vez recorrido todas las imagenes del nodo, actualizo su estado a finalizado
            nodoActual.setEstado(Estado.FINALIZADO)
            self.manager.escribirNodo(nodoActual)

        driver.close()
        print(self.name+" EL PRODUCTOR FINALIZO")

    #Image Iterator
    def iterate(self, driver, nodoActual):
        try:    
            # elementoFinal = driver.find_element_by_class_name(Config.HTML['endClass'])
            # boton = driver.find_element_by_class_name(Config.HTML['endVerMasClass'])
            elementoFinal = driver.find_element(By.CLASS_NAME, Config.HTML['endClass'])
            #boton = driver.find_element(By.CLASS_NAME, Config.HTML['endVerMasClass'])
        except Exception as e:
            print(self.name + ": No se encontro elemento final o boton de cargar mas imagenes")
            return
        
        offset = 0 
        lista = driver.find_elements(By.XPATH ,Config.HTML['xpath']) # log ACTUALIZADO
        print("Se encontraron una cantidad de thumbnails igual a: "+str(len(lista)))
        hay_imagenes = True
        while (hay_imagenes):
            for i in range(offset,len(lista)):
                #Si mi trigger de finish se activo, entonces dejo de iterar
                if self.stopper:
                    break
        
                #Obtengo el elemento de la lista para luego clickearlo
                print(self.name + ": CLICKEANDO EN LA IMG NRO: "+str(i))
                elemento = lista[i]
                try:
                    elemento.click()
                except Exception as ex:
                    print(self.name + ": No se pudo clickear en la imagen")
                    continue
                nodoActual.addCantidadRecorridos(1) #Le sumo 1 a cantidad recorridos
                #El valor de la variable exito la voy a utilizar luego para escribir la muestra de tiempo
                exito = self.extractInfo(driver, nodoActual)
            
            if self.stopper:
                break
            
            offset = len(lista)
            lista = driver.find_elements(By.XPATH ,Config.HTML['xpath'])
            if(len(lista) == offset):
                if(False):#boton.is_displayed()):  # TODO  esto lo voy a borrar, tengo que investigar que pasa con el boton que no aparece
                    print(self.name + ": Apretando el boton de VER MAS")
                    try:
                        boton.click()
                    except Exception as ex:
                        hay_imagenes = False
                        print(self.name + ": No se pudo clickear el boton para ver mas imagenes")
                elif(elementoFinal.is_displayed()):
                    print(self.name + ": Termino de recorrer la pagina")
                    hay_imagenes = False
                else:
                    print(self.name + ": Esperando mas imagenes")

    def extractInfo(self, driver, nodoActual):
        try:
            #Espera a que se cargue la imagen con un timeout
            image_present = EC.presence_of_element_located((By.CSS_SELECTOR, Config.HTML['imgClass']))
            WebDriverWait(driver, self.waitLoadTimeOut).until(image_present)
            
            #Una vez cargada la imagen, se guarda su link extrayendo el atributo "src" 
            imagen = driver.find_element(By.CSS_SELECTOR, Config.HTML['imgClass'])
            linkImagen = imagen.get_attribute("src")

            try:
                #Espera a que este presente el boton de "ver mas" de la imagen con un timeout
                seeMore_present = EC.presence_of_element_located((By.CSS_SELECTOR, Config.HTML['verMasClass']))
                WebDriverWait(driver, self.waitLoadTimeOut).until(seeMore_present)
                
                #Si aparece el boton, guardo el link al que me lleva el boton
                urlVerMas = driver.find_element(By.CSS_SELECTOR, Config.HTML['verMasClass']).get_attribute("href")
                nodoHijo = Node(query=nodoActual.getQuery(), url=urlVerMas, imgLink=linkImagen, nivel = nodoActual.getNivel() + 1, padre = nodoActual)
                # print(self.name + ": ANTES ")
                self.manager.addNodoProducer(nodoHijo)
                print(self.name + ": se pudo ingresar el elemento " + linkImagen)
                return True

            except TimeoutException as ex:
                print(self.name + ": Time out waiting See More button to load")
                nodoActual.addCantidadTimeouts(1) 
                return False

        except TimeoutException as ex:
            print(self.name + ": Time out waiting image to load")
            nodoActual.addCantidadTimeouts(1)
            return False
        

class Consumer(threading.Thread):
    def __init__(self, manager, path, name=None, responseTimeOut = 5):
        Thread.__init__(self,name=name)
        self.manager = manager
        self.path = path #Direccion en la que se guardan las imagenes descargadas
        self.responseTimeOut = responseTimeOut
        self.stopper = False #Detiene el consumer en caso de setearse en True
        self.mime = magic.Magic(mime=True)
        if not os.path.exists(path):
            os.makedirs(path)

    def apagar(self):
        self.stopper = True
    
    def run(self):
        print("CONSUMIDOR CON NOMBRE: " + self.name + ", COMIENZA")
        while True:
            if self.stopper:
                print(self.name+": SE DETUVO EL CONSUMIDOR")
                break
            print(self.name+": Tratando de obtener la imagen")
            nodoActual = self.manager.getNodoConsumer()
            if(nodoActual == None):
                print(self.name+": Se obtuvo un nodo NONE.")
                continue
            print(self.name+": Se obtuvo una imagen")
            exitoDescarga = self.descargarImg(nodoActual)
            if(exitoDescarga):
                self.manager.addNodoConsumer(nodoActual)
            else:
                nodoActual.getPadre().addCantidadDownloadFails(1)
        print(self.name+" EL CONSUMIDOR FINALIZO")

    def descargarImg(self, nodoActual):
        print(self.name + ": Consumiendo: " + nodoActual.getImageLink())
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:50.0) Gecko/20100101 Firefox/50.0'} #Revisar Esta bien este user?
            response = requests.get(nodoActual.getImageLink(), headers=headers, timeout=self.responseTimeOut)
            if response.status_code == 200: #Revisar, que pasa si aun poniendo el header me da otro codigo
                completePath = self.path + nodoActual.getReferencia()
                fp = open(completePath, 'wb')
                fp.write(response.content)
                fp.close()
                return self.agregarExtension(nodoActual, completePath)
            else:
                print(self.name + ": Response distinto que 200")
                return False  
        except Exception:
            print(self.name + ": No se pudo descargar la imagen")
            return False

    def agregarExtension(self, nodoActual, completePath):
        file_type = self.mime.from_file(completePath).split('/')[1]
        if(file_type != None):
            renamedPath = completePath+'.'+file_type
            os.rename(completePath, renamedPath) 
            nodoActual.setExtension(file_type)
            nodoActual.setPath(renamedPath)
            return True
        else:
            print(self.name + ": No se pudo obtener la extension de la imagen")
            os.remove(completePath)
            return False


class DistanceCalculator(threading.Thread):
    def __init__(self, manager, name=None, responseTimeOut = 5):
        Thread.__init__(self,name=name)
        self.manager = manager
        self.responseTimeOut = responseTimeOut
        self.stopper = False #Detiene el consumer en caso de setearse en True

    def apagar(self):
        self.stopper = True
    
    def run(self):
        print("DISTANCE CALCULATOR CON NOMBRE: " + self.name + ", COMIENZA")
        while not self.stopper:
            print(self.name+": Tratando de obtener el nodo")
            nodoActual = self.manager.getNodoDistanceCalculator()
            if(nodoActual == None):
                print(self.name+": Se obtuvo un nodo NONE.")
                continue
            print(self.name+": Se obtuvo un nodo")
            exitoDistancia = self.calcularDistancia(nodoActual)
            if(exitoDistancia):
                self.manager.addNodoDistanceCalculator(nodoActual)
            else:
                nodoActual.getPadre().addCantidadSvddFails(1)
        print(self.name+" EL DISTANCE CALCULATOR FINALIZO")

    def calcularDistancia(self, nodoActual):
        print(self.name + ": Calculando distancia de: " + nodoActual.getReferencia())
        try:
            files = {
            'image': open(nodoActual.getPath(), 'rb'),
            }
        except Exception as e:
            print(self.name + ": No se pudo abrir la imagen para calcular la distancia")
            return False
        try:
            response = requests.post(Config.AnomalyDetection['url'], files=files, timeout=self.responseTimeOut)
            jsonResponse = response.json()
            if(jsonResponse['distance'] != None):
                print(self.name + ": La distancia es: " + str(jsonResponse['distance']))
                nodoActual.setDistance(jsonResponse['distance'])
                return True
            else:
                return False

        except RequestException as ex:
            print(self.name + ": Error al calcular la distancia")
            return False


class Manager():
    def __init__(self, queries, cantidadImagenes, path, cantidadProducers = 1, cantidadConsumers = 1, cantidadDistanceCalculators = 1, 
                 name=None, anchura = 0, queueTimeout = 5, queueSize = 10, headless = True):
        # Thread.__init__(self, name=name)
        self.cantImagenesSolicitadas = cantidadImagenes
        self.path = path
        self.cantidadProducers  = cantidadProducers
        self.cantidadConsumers = cantidadConsumers
        self.cantidadDistanceCalculators = cantidadDistanceCalculators
        self.anchura = anchura #anchura del arbol de nodos. Cuando es cero, no hay limite de hijos. 
        self.queueTimeout = queueTimeout
        self.name = name
        self.queueSize = queueSize #Tamanio de las colas de nodos.
        self.headless = headless

        #Creo las estructuras internas del Manager
        self.queriesIniciales = queries #Es una lista con tipo Query
        self.contenedorNodos =  dict() #Estructura en la cual voy a ir guardando todos los  nodos
        self.nodosExitosos =  dict() #Estructura en la cual voy a ir guardando los nodos exitosos
        self.listaProducers = list()
        self.listaConsumers = list()
        self.listaDistanceCalculators = list()
        self.producerQueue = Queue() #La cola del producer no se limita debido a que el productor consume a muchisima menor frecuencia que de lo que produce
        self.consumerQueue = Queue() #REVISAR puedo limitar el tamanio del buffer
        self.distanceCalculatorQueue = Queue()

        #lockers
        self.lockContenedor = threading.Lock()
        self.lockExitosos = threading.Lock()

        if Config.General['trigger_medidas_tiempo']:
            #Tiempo de throughput
            self.tiempo = time.time()


    # -------- Getters de estructuras --------

    def getNodosExitosos(self):
        return self.nodosExitosos
    
    def getQueriesIniciales(self):
        return self.queriesIniciales

    # -------- Interfaz para las demas clases --------

    def getNodoProducer(self):
        try:
            nodoActual = self.producerQueue.get(timeout=self.queueTimeout)
            return nodoActual
        except Exception:
            return None


    def addNodoProducer(self, nodo):
        with self.lockContenedor:
            if(self.contenedorNodos.get(nodo.getReferencia()) == None):
                self.contenedorNodos[nodo.getReferencia()] = nodo
                self.consumerQueue.put(nodo)
                # print(self.name + ": Se agrego a la queue de consumer con tamanio "+str(self.consumerQueue.qsize()))
            else:
                nodo.getPadre().addCantidadRepetidos(1)
                print(self.name + ": REPETIDO")

    def getNodoConsumer(self):
        try:
            nodoActual = self.consumerQueue.get(timeout=self.queueTimeout)
            return nodoActual
        except Exception:
            return None

    def addNodoConsumer(self, nodo):
        self.distanceCalculatorQueue.put(nodo)
        pass

    def getNodoDistanceCalculator(self):
        try:
            nodoActual = self.distanceCalculatorQueue.get(timeout=self.queueTimeout)
            return nodoActual
        except Exception:
            return None

    def addNodoDistanceCalculator(self, nodo):
        if(nodo.getDistance() >= Config.General['valorPoda']):
            nodo.getPadre().addHijo(nodo)
            self.producerQueue.put(nodo)
            with(self.lockExitosos):
                self.nodosExitosos[nodo.getReferencia()] = nodo
                if Config.General['trigger_medidas_tiempo']:
                    throughputTime_end = time.time() #TIME 
                    # Escribo muestras de tiempo
                    with open(Config.Files['csvThroughput'], 'a') as f:
                        csv.writer(f).writerow([throughputTime_end-self.tiempo])
                    self.tiempo = time.time()
                if(len(self.nodosExitosos)>= self.cantImagenesSolicitadas):
                    self.__apagar()
        else:
            nodo.getPadre().addCantidadPodados(1)

    # -------- Escribir un nodo en los csv del output --------

    def escribirNodo(self, nodo): #TODO
        with(self.lockExitosos):
            with open(Config.Files['csvNodosArbol'], 'a') as nodesFile:
                refPadre = nodo.getPadre().getReferencia() if nodo.getPadre() != None else ''
                nodesRow = [nodo.getReferencia(), nodo.getQuery().to_string(), refPadre, nodo.getNivel(), nodo.getUrl(), nodo.getPath(), nodo.getDistance(), nodo.getImgExitosas(), nodo.getCantidadRecorridos(),  nodo.getCantidadTimeouts(),nodo.getCantidadRepetidos(), nodo.getCantidadDownloadFails(), nodo.getCantidadSvddFails()]
                csv.writer(nodesFile).writerow(nodesRow)
            with open(Config.Files['csvImagenes'], 'a') as imgFile:
                listaHijos = nodo.getHijos()
                self.nodosExitosos[nodo.getReferencia()] = nodo
                for nodoHijo in listaHijos:
                    imgRow = [nodoHijo.getReferencia(), nodoHijo.getQuery().to_string(), nodo.getReferencia(), nodoHijo.getNivel(), nodoHijo.getUrl(), nodoHijo.getPath(), nodoHijo.getDistance()]
                    csv.writer(imgFile).writerow(imgRow)



    def __inicializarThreads(self):
        #Inicializo los producers y consumers y los guardo en una lista
        for i in range(0, self.cantidadProducers):
            prod = Producer(manager=self, name="p-"+str(i), headless=self.headless)
            self.listaProducers.insert(i, prod)
            prod.start()
        print(self.name + ": Cantidad producers: "+str(len(self.listaProducers)))

        for i in range(0, self.cantidadConsumers):
            cons = Consumer(manager=self, path=self.path, name="c-"+str(i))
            self.listaConsumers.insert(i, cons)
            cons.start()
        print(self.name + ": Cantidad consumers: "+str(len(self.listaConsumers)))

        for i in range(0, self.cantidadDistanceCalculators):
            dc = DistanceCalculator(manager=self, name="dc-"+str(i))
            self.listaDistanceCalculators.insert(i, dc)
            dc.start()
        print(self.name + ": Cantidad consumers: "+str(len(self.listaDistanceCalculators)))

    def __apagar(self):
        for prod in self.listaProducers:
            prod.apagar()
        
        for cons in self.listaConsumers:
            cons.apagar()
        
        for dc in self.listaDistanceCalculators:
            dc.apagar()

    # #Recorre todos los nodos del ARBOL y devuelve TRUE si estan todos finalizados
    # def __corroborarNodosFinalizados(self):

    def comenzar(self):
        self.__inicializarThreads()

        #Por cada query ingresada, creo el tipo Nodo y lo distribuyo a los producers
        for query in self.queriesIniciales: 
            url = query.getUrl()
            print(self.name + ": INGRESANDO LA QUERY: " + url)
            nodoRaiz = Node(query=query, url=url, nivel = 0)
            self.contenedorNodos[nodoRaiz.getReferencia()] = nodoRaiz
            self.nodosExitosos[nodoRaiz.getReferencia()] = nodoRaiz #REVISAR ver si poner las queries en nodosExitosos esta bien, ya que esto lo hago para que luego se puedan poner estos nodos en el archivo
            self.producerQueue.put(nodoRaiz)
        
        #REVISAR BORRAR
        if(Config.General['trigger_tiempo']):
            time.sleep(Config.General['tiempoCronometro'])
            self.__apagar()

        for prod in self.listaProducers:
            print(self.name + ": ESPERANDO A QUE TERMINE: "+prod.name)
            prod.join()
        
        for consumers in self.listaConsumers:
            print(self.name + ": ESPERANDO A QUE TERMINE: "+consumers.name)
            consumers.join()
            
        for dc in self.listaDistanceCalculators:
            print(self.name + ": ESPERANDO A QUE TERMINE: "+dc.name)
            dc.join()
        print(self.name + ": MANAGER TERMINO")
     

def setup_logger(name, log_file, level=logging.DEBUG):
    handler = logging.FileHandler(log_file, mode='w')        
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger   

def resetCsvMeasureTime():
    header = ['Cantidad Imagenes, Total time']
    with open(Config.Files['csvTimeMeasure'], 'w') as f:
        csv.writer(f).writerow(header)

    header = ['Tiempo de salida por nodo']
    with open(Config.Files['csvThroughput'], 'w') as f:
        csv.writer(f).writerow(header)

def resetCsvOutput():
    imgHeader = ['Referencia','Query','Padre','Nivel','URL','Path','Distance']
    nodesHeader = ['Referencia','Query','Padre','Nivel','URL','Path','Distance','Imagenes Exitosas','Imagenes Recorridas','TimeOuts','Repetidas','Descargas fallidas','Svdd Fallidas']
    with open(Config.Files['csvImagenes'], 'w') as imgFile:
        with open(Config.Files['csvNodosArbol'], 'w') as nodesFile:
            csv.writer(imgFile).writerow(imgHeader)
            csv.writer(nodesFile).writerow(nodesHeader)

    

def crearArchivoNodos(nodos):
    imgHeader = ['Referencia','Query','Padre','Nivel','URL','Path','Distance']
    nodesHeader = ['Referencia','Query','Padre','Nivel','URL','Path','Distance','Imagenes Exitosas','Imagenes Recorridas','TimeOuts','Repetidas','Descargas fallidas','Svdd Fallidas']
    with open(Config.Files['csvImagenes'], 'w') as imgFile:
        with open(Config.Files['csvNodosArbol'], 'w') as nodesFile:
            csv.writer(imgFile).writerow(imgHeader)
            csv.writer(nodesFile).writerow(nodesHeader)
            for key, nodo in nodos.items():
                refPadre = ''
                if(nodo.getPadre() != None):
                    refPadre = nodo.getPadre().getReferencia()
                imgRow = [nodo.getReferencia(), nodo.getQuery().to_string(),refPadre, nodo.getNivel(), nodo.getUrl(), nodo.getPath(), nodo.getDistance()]
                csv.writer(imgFile).writerow(imgRow)
                if(nodo.getEstado() != Estado.SIN_ASIGNAR):
                    nodesRow = [nodo.getReferencia(), nodo.getQuery().to_string(), refPadre, nodo.getNivel(), nodo.getUrl(), nodo.getPath(), nodo.getDistance(), nodo.getImgExitosas(), nodo.getCantidadRecorridos(),  nodo.getCantidadTimeouts(),nodo.getCantidadRepetidos(), nodo.getCantidadDownloadFails(), nodo.getCantidadSvddFails()]
                    csv.writer(nodesFile).writerow(nodesRow)


#Main
def main():
    #config_values = load_config()
    Config.load_config()

    #Revisar, ver bien como andaria este proyecto con otros motores
    # Se podria hacer varias de estas sentencias en un if con otros motores
    chromedriver_autoinstaller.install()

    if Config.General['trigger_medidas_tiempo']:
        resetCsvMeasureTime()
        globalTime_start = time.time() #TIME 
    
    resetCsvOutput()
    

    manager = Manager(queries=Config.Queries, cantidadImagenes=Config.General['cantidadImagenes'], path=Config.Files['outputPath'], name="manager", cantidadProducers= Config.General['cantidad_productores'], 
                      cantidadConsumers=Config.General['cantidad_consumidores'], cantidadDistanceCalculators=Config.General['cantidad_distance_calculators'], headless=Config.General['headless'])
    manager.comenzar()

    if Config.General['trigger_medidas_tiempo']:
        globalTime_end = time.time() #TIME 
        timeRow = [str(Config.General['cantidadImagenes']), str(globalTime_end-globalTime_start)]
        with open(Config.Files['csvTimeMeasure'], 'a') as f:
            csv.writer(f).writerow(timeRow)

main()
 