import subprocess
import sys
import os

REPO_URL = "https://github.com/JorgeJuajinoy/lotterypython.git"

def run_command(command, description):
    print(f"\n[Ejecutando] {description}...")
    try:
        # Ejecutamos comando capturando salida para mejor diagnóstico
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.stdout:
            print(result.stdout.strip())
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error en: {description}")
        if e.stdout:
            print(f"Salida estándar:\n{e.stdout}")
        if e.stderr:
            print(f"Salida de error:\n{e.stderr}")
        return False

def main():
    # 1. Verificar si git está instalado
    if not run_command("git --version", "Verificar instalación de Git"):
        print("Git no está instalado o no está en el PATH del sistema.")
        return

    # 2. Inicializar repositorio si no existe .git
    if not os.path.exists(".git"):
        if not run_command("git init", "Inicializar repositorio Git local"):
            return
        # Definir la rama predeterminada como 'main'
        run_command("git branch -M main", "Establecer rama principal a main")

    # 3. Configurar remote
    # Intentamos remover si ya existe para evitar conflictos
    subprocess.run("git remote remove origin", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not run_command(f"git remote add origin {REPO_URL}", f"Conectar con repositorio remoto ({REPO_URL})"):
        return

    # 4. Agregar archivos al area de preparación (Staging)
    if not run_command("git add .", "Preparar archivos (stage)"):
        return

    # 5. Hacer commit
    # Verificamos si hay cambios para hacer commit
    try:
        status_check = subprocess.run("git status --porcelain", shell=True, stdout=subprocess.PIPE, text=True)
        if not status_check.stdout.strip():
            print("\n[OK] No hay cambios nuevos que confirmar (commit). Todo está al día.")
        else:
            commit_msg = "Actualización automática del sistema Lottery Loop"
            if not run_command(f'git commit -m "{commit_msg}"', "Confirmar cambios (commit)"):
                return
    except Exception as e:
        print(f"Error al verificar estado: {e}")
        return

    # 6. Intentar subir los cambios (push)
    print("\n[Ejecutando] Subiendo cambios a GitHub (git push)...")
    print("Nota: Si es la primera vez, es posible que se abra una ventana para iniciar sesión en tu cuenta de GitHub.")
    
    # Ejecutamos el push interactivo para que el usuario pueda autenticarse si el sistema lo pide
    try:
        result = subprocess.run("git push -u origin main", shell=True, check=True)
        print("\n[SUCCESS] Codigo subido con exito a GitHub!")
        print(f"Puedes verlo en: {REPO_URL.replace('.git', '')}")
    except subprocess.CalledProcessError:
        print("\nError al subir cambios a GitHub.")
        print("Sugerencias de solución:")
        print("1. Verifica que tienes conexión a internet.")
        print("2. Asegúrate de tener permisos de escritura en el repositorio.")
        print("3. Si GitHub te pide credenciales, usa tu Token de Acceso Personal (PAT) o inicia sesión mediante el navegador.")
        print("4. Si la rama remota contiene cambios que no tienes localmente, ejecuta: git pull origin main --rebase")

if __name__ == "__main__":
    main()
