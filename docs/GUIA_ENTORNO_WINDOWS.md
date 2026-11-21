# Preparar el entorno (Windows 10/11 + WSL 2)

Equipo de referencia: i5-1035G1 (4 núcleos / 8 hilos), **8 GB de RAM**, 1.14 TB de disco.
La RAM es el punto crítico: Windows ≈ 3 GB + WSL 4 GB. **Cierra Chrome, Teams y similares antes de medir.**

> **Dónde corre qué:** solo el equipo que hará las mediciones oficiales necesita Minikube. Los demás pueden trabajar
> con `pytest` y `docker compose` (mucho más ligero). Todas las mediciones oficiales deben salir del mismo equipo.

## 1. Virtualización
Administrador de tareas → Rendimiento → CPU → debe decir **Virtualización: Habilitada**. Si no, actívala en la BIOS.

## 2. Instalar WSL 2 (PowerShell como administrador)
```powershell
wsl --install -d Ubuntu-22.04
```
Reinicia si lo pide y crea tu usuario de Linux.

## 3. Limitar memoria de WSL (evita que Docker congele Windows)
Crea `C:\Users\TU_USUARIO\.wslconfig`:
```ini
[wsl2]
memory=4GB
processors=4
swap=2GB
```
> Corrección respecto a la primera versión del plan: `processors=4` (no 2). Con 2 procesadores k6 y Minikube se
> pelean por CPU y las mediciones salen distorsionadas. Windows ve 8 hilos, así que 4 deja la mitad libre.
> Si Windows se pone muy lento, baja a 3 y usa `MINIKUBE_CPUS=2`.

## 4. Activar systemd (en Ubuntu)
```bash
echo -e "[boot]\nsystemd=true" | sudo tee /etc/wsl.conf
```
En PowerShell: `wsl --shutdown`. Abre Ubuntu otra vez y verifica con `free -h` (≈ 4 GB) y `nproc` (4).

## 5. Clonar el repositorio (siempre en `~/`, NO en `/mnt/c`)
```bash
cd ~
git clone git@github.com:USUARIO/telemetria-iot.git     # ver sección 7 si aún no hay clave SSH
cd telemetria-iot
bash scripts/setup_wsl.sh        # Docker Engine, kubectl, Minikube, k6, entorno virtual de Python
```
Cierra y abre la terminal (para el grupo `docker`) y comprueba:
```bash
bash scripts/verificar_entorno.sh
```
Usamos **Docker Engine dentro de Ubuntu**, no Docker Desktop (ahorra ~1 GB de RAM).

## 6. Probar sin Kubernetes
```bash
.venv/bin/python -m pytest -q
docker compose up --build -d
curl localhost:8000/health/live
docker compose down -v
```

## 7. GitHub (primera vez)
**Una persona (administrador):**
1. Crear en GitHub un repositorio **privado** `telemetria-iot` **vacío** (sin README).
2. En su equipo, dentro de la carpeta del proyecto:
   ```bash
   git config --global user.name "Tu Nombre"; git config --global user.email "tu@correo.com"
   git init -b main && git add . && git commit -m "chore: proyecto base de telemetria IoT"
   git remote add origin git@github.com:USUARIO/telemetria-iot.git
   git push -u origin main
   ```
3. *Settings → Collaborators*: agregar a los otros tres con permiso **Write**.
4. *Settings → Branches → Add rule* para `main`: exigir Pull Request con 1 aprobación.

**Cada integrante:** `ssh-keygen -t ed25519` → pegar `~/.ssh/id_ed25519.pub` en GitHub → *Settings → SSH keys* → `git clone …`.

**Flujo diario (nadie trabaja directo en `main`):**
```bash
git checkout main && git pull
git checkout -b feat/nombre-corto
# ... trabajar ...
git add -A && git commit -m "feat: descripcion"
git push -u origin feat/nombre-corto      # abrir Pull Request en GitHub; otro integrante revisa y hace merge
```
Los PR dejan evidencia de la contribución individual para la defensa.

## 8. Desplegar en Minikube
```bash
bash scripts/deploy.sh
export BASE_URL=http://$(minikube ip):30080
curl $BASE_URL/health/live
kubectl -n telemetria-iot get pods
```
`deploy.sh` inicia Minikube con 3 CPUs y 2800 MB (cámbialo con `MINIKUBE_CPUS` / `MINIKUBE_MEMORY`),
construye las imágenes dentro del clúster y aplica los YAML. Tras cambiar código, vuelve a ejecutarlo.

## 9. Problemas frecuentes
| Síntoma | Causa / solución |
|---|---|
| `permission denied` con docker | No reabriste la terminal tras `usermod -aG docker`. |
| `docker: Cannot connect to the Docker daemon` | `sudo systemctl start docker` (¿activaste systemd? paso 4). |
| Windows se congela | Cierra apps; baja `memory`/`processors` en `.wslconfig`; `MINIKUBE_MEMORY=2400mb`. |
| Pod `OOMKilled` | Sube el límite de memoria en `k8s/*.yaml` o baja réplicas; cierra otras apps. |
| `ImagePullBackOff` / `ErrImageNeverPull` | Falta construir imágenes: `bash scripts/deploy.sh`. |
| `curl` a `minikube ip:30080` no responde | `minikube status`; `kubectl -n telemetria-iot get svc api`; ¿usas Docker Desktop en vez de Engine? |
| `kubectl top` dice "metrics not available" | Espera ~1 min tras `minikube addons enable metrics-server`. |
| Todo muy lento | ¿Estás en `/mnt/c`? Mueve el repo a `~/`. |
| Empezar de cero | `minikube delete` y luego `bash scripts/deploy.sh`. |
