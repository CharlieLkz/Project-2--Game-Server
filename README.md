
# Card-Jitsu LAN: Servidor Autoritativo con Telemetría en Tiempo Real 🥋🔥💧❄️
![Python Version](https://img.shields.io/badge/Python-3.8%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Linux-Ubuntu-orange?style=for-the-badge&logo=ubuntu&logoColor=white)
![Network](https://img.shields.io/badge/Protocol-TCP%20%2F%20Sockets-green?style=for-the-badge)
![Academic](https://img.shields.io/badge/Asignatura-Redes-red?style=for-the-badge)

Este repositorio contiene la implementación completa de una arquitectura **Cliente-Servidor Autoritativa** para jugar **Card-Jitsu** (el clásico minijuego de Club Penguin) a través de una red de área local (LAN) inalámbrica. El sistema está desarrollado íntegramente en Python utilizando sockets nativos de bajo nivel, programación concurrente mediante hilos (`threading`) y serialización de datos en formato JSON para la capa de aplicación.

El enfoque principal del proyecto es puramente académico y de ingeniería de telecomunicaciones, demostrando la gestión de conexiones concurrentes TCP, el manejo de estados compartidos en el servidor y el diseño de un protocolo de comunicación personalizado.

---

## 🏗️ Arquitectura del Sistema

El proyecto implementa un modelo de **Servidor Autoritativo**, lo que significa que toda la lógica de juego, validación de reglas, estado de las manos de los jugadores y resolución del combate se ejecuta exclusivamente en el host central. Los clientes actúan como terminales "tontas" que se encargan únicamente de renderizar la interfaz gráfica en texto (TUI) y enviar las intenciones de entrada del usuario.

    ```text
           [ Cliente 1 (Jugador 1) ]           [ Cliente 2 (Jugador 2) ]
              IP: 192.168.1.X                     IP: 192.168.1.Y
                     │                                   │
                     └───► [ Sockets TCP (Capa 4) ] ◄────┘
                                      │
                                      ▼
                            [ Módem WiFi / Router ]
                                      │
                                      ▼
                         [ Servidor Central (Host) ]
                               IP: 192.168.1.Z
                    ┌───────────────────────────────────┐
                    │ • Socket Listener                 │
                    │ • Threading Engine (Concurrencia) │
                    │ • Dashboard de Telemetría Realtime│
                    └───────────────────────────────────┘
ustificación de Protocolos (Modelo OSI)

    Capa de Transporte (TCP): Se seleccionó TCP sobre UDP debido a que la naturaleza del juego por turnos exige que ningún paquete se pierda ni se desordene. Un byte faltante corrompería la sincronización del estado de la partida.

    Capa de Aplicación (JSON Custom Protocol): Los mensajes se estructuran en diccionarios JSON serializados a bytes. Esto permite escalabilidad en la carga útil (payload), transportando metadatos complejos como estructuras de cartas, códigos de estado y telemetría.

📊 Panel de Control del Servidor (Dashboard)

A diferencia de los servidores silenciosos convencionales, el script server.py integra una interfaz de visualización en tiempo real para el administrador de la red. La pantalla se actualiza mostrando un desglose detallado de los sockets activos:

    Identificación de Sockets: Mapeo de dirección IP y puertos efímeros de origen asignados por el sistema operativo a cada cliente.

    Métricas de Tráfico: Contadores dinámicos de bytes transmitidos (Tx) y recibidos (Rx).

    Inspección de Payload: Visualización en crudo de la última trama JSON recibida para auditoría del tráfico de aplicación.

⚙️ Requisitos e Instalación
Prerrequisitos

    Sistema Operativo basado en Linux (Probado exitosamente en entorno Ubuntu).

    Python 3.8 o superior instalado en todas las estaciones de trabajo.

Clonación del Repositorio

Para desplegar este proyecto en los entornos locales, ejecute el siguiente comando en la terminal:
Bash

git clone [https://github.com/TuUsuario/card-jitsu-lan-tcp.git](https://github.com/TuUsuario/card-jitsu-lan-tcp.git)
cd card-jitsu-lan-tcp

🚀 Guía de Despliegue en Red Local
Paso 1: Configuración de Red en el Servidor

    Conecte el equipo que actuará como Servidor al módem WiFi.

    Identifique su dirección IP local en la red mediante el comando:
    Bash

    ip a

3. Abra el archivo `server.py` y asegúrese de que el host apunte a su IP local o a `'0.0.0.0'`.

### Paso 2: Lanzamiento del Servidor Central
Ejecute el script del servidor. Este quedará en estado de escucha pasiva esperando a los clientes:
```bash
python3 server.py

Paso 3: Conexión de los Clientes

    En las otras dos computadoras conectadas a la misma red WiFi, abra el archivo client.py.

    Configure la variable con la dirección IP exacta obtenida en el Paso 1.

    Inicie el cliente en la terminal de cada estación:
    Bash

    python3 client.py


---

## 👨‍💻 Autor

**Carlos Alberto Lazcano Vásquez**
Universidad Nacional Autónoma de México (UNAM) - Facultad de Ingeniería
*Proyecto de Ingeniería en Telecomunicaciones*
