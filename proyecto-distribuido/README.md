# Sistema Distribuido de Consulta y Registro de Información

API idéntica desplegada en dos servidores Linux con distinto kernel/distribución, sincronización automática vía REST/HTTP+JSON.

| Servidor | SO | IP | Puerto |
|---|---|---|---|
| Servidor 1 | Ubuntu 24.04 LTS | 192.168.56.10 | 8000 |
| Servidor 2 | Rocky Linux 9 | 192.168.56.11 | 8000 |

## 0. Red virtual (VirtualBox) — una sola vez, en el host

1. VirtualBox → **Archivo → Herramientas de red del host** → Crear (crea `vboxnet0`, DHCP deshabilitado).
2. En **cada VM** (Ubuntu y Rocky): Configuración → Red → **Adaptador 2** → Habilitar → "Adaptador solo-anfitrión" → `vboxnet0`. Dejar el Adaptador 1 como NAT (para salida a internet e instalar paquetes).
3. Encender ambas VMs.

## 1. Configurar IP fija en cada servidor

**Servidor 1 (Ubuntu 24.04) — interfaz del adaptador 2, normalmente `enp0s8`:**
```bash
ip a   # identificar el nombre de la interfaz del segundo adaptador
sudo tee /etc/netplan/99-labdist.yaml > /dev/null <<'EOF'
network:
  version: 2
  ethernets:
    enp0s8:
      addresses: [192.168.56.10/24]
EOF
sudo netplan apply
```

**Servidor 2 (Rocky Linux 9) — interfaz normalmente `enp0s8`:**
```bash
nmcli con show   # identificar el nombre de conexión del segundo adaptador
sudo nmcli con mod enp0s8 ipv4.addresses 192.168.56.11/24 ipv4.method manual
sudo nmcli con up enp0s8
```

Verificar conectividad cruzada:
```bash
ping -c3 192.168.56.11    # desde Servidor 1
ping -c3 192.168.56.10    # desde Servidor 2
```

## 2. Instalar Docker

**Servidor 1 (Ubuntu 24.04):**
```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER && newgrp docker
```

**Servidor 2 (Rocky Linux 9):**
```bash
sudo dnf -y install dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo
sudo dnf -y install docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER && newgrp docker
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

En Ubuntu, si UFW está activo:
```bash
sudo ufw allow 8000/tcp
```

## 3. Obtener el código en ambos servidores

```bash
git clone <URL_DEL_REPOSITORIO_GITHUB> proyecto-distribuido
cd proyecto-distribuido
```

## 4. Configurar el archivo de entorno según el servidor

**Servidor 1:**
```bash
cp .env.servidor1 .env
```

**Servidor 2:**
```bash
cp .env.servidor2 .env
```

## 5. Levantar los servicios (API + PostgreSQL en Docker)

Ejecutar en **ambos servidores**:
```bash
docker compose up -d --build
docker compose ps
docker compose logs -f api    # Ctrl+C para salir del seguimiento de logs
```

## 6. Verificación funcional

**Verificar disponibilidad de cada servidor (local):**
```bash
curl http://localhost:8000/
curl http://localhost:8000/estado
```

**Verificar comunicación bidireccional (desde Servidor 1):**
```bash
curl http://192.168.56.11:8000/            # alcanza al Servidor 2
curl http://192.168.56.10:8000/estado | jq  # "servidor_par.disponible" debe ser true
```

**Registrar un dato en el Servidor 1 y confirmarlo en el Servidor 2:**
```bash
curl -X POST http://192.168.56.10:8000/registrar \
  -H "Content-Type: application/json" \
  -d '{"dato": "Prueba desde servidor 1"}'

curl http://192.168.56.11:8000/consultar    # el registro debe aparecer sincronizado
```

**Registrar un dato en el Servidor 2 y confirmarlo en el Servidor 1:**
```bash
curl -X POST http://192.168.56.11:8000/registrar \
  -H "Content-Type: application/json" \
  -d '{"dato": "Prueba desde servidor 2"}'

curl http://192.168.56.10:8000/consultar
```

## 7. Acceso desde el host (VMware/VirtualBox) fuera de las VMs

Con la red solo-anfitrión (`vboxnet0` / `192.168.56.0/24`), el host de VirtualBox puede acceder directamente sin port-forwarding:
```
http://192.168.56.10:8000/
http://192.168.56.11:8000/
```
Basta con abrir esas URLs en el navegador del host o consultarlas con Postman.

## Endpoints implementados

| Método | Endpoint | Función |
|---|---|---|
| GET | `/` | Verificar disponibilidad e identificar el servidor |
| GET | `/estado` | Estado propio + estado de conexión con el servidor par |
| POST | `/registrar` | Registrar información (persiste local y sincroniza al par) |
| GET | `/consultar` | Consultar toda la información almacenada localmente |
| POST | `/sincronizar` | Recibe y persiste un registro proveniente del servidor par |

## Comandos de administración

```bash
docker compose down            # detener servicios
docker compose down -v         # detener y borrar datos de PostgreSQL
docker compose restart api     # reiniciar solo la API
```
