#-----------------------------------------------
# Convertidor de Imagenes
#-----------------------------------------------

from PIL import Image, ImageFile
import os
import shutil

# Pillow sometimes fails on truncated images; enable loading anyway
ImageFile.LOAD_TRUNCATED_IMAGES = True


def _prepare_dest(ruta_destino: str) -> str:
    """Asegura que la carpeta de destino exista dentro del repositorio.

    - Si `ruta_destino` es relativa, se interpreta respecto a la raíz del repo.
    - Crea el directorio padre si no existe.
    - Devuelve la ruta absoluta final a usar para guardar.
    """
    if ruta_destino is None:
        raise ValueError("ruta_destino no puede ser None")

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

    if not os.path.isabs(ruta_destino):
        ruta_abs = os.path.join(repo_root, ruta_destino)
    else:
        ruta_abs = ruta_destino

    parent = os.path.dirname(ruta_abs)
    if parent == '':
        parent = os.path.join(repo_root, 'destino')
        ruta_abs = os.path.join(parent, os.path.basename(ruta_abs))

    os.makedirs(parent, exist_ok=True)
    return ruta_abs


def _find_ffmpeg() -> str | None:
    """Intentar localizar el ejecutable ffmpeg."""
    env_path = os.environ.get('FFMPEG_PATH')
    if env_path:
        env_path = os.path.abspath(env_path)
        if os.path.isfile(env_path):
            return env_path
        if os.path.isdir(env_path):
            for candidate in ('ffmpeg.exe', 'ffmpeg'):
                maybe = os.path.join(env_path, candidate)
                if os.path.isfile(maybe):
                    return maybe

    for name in ('ffmpeg', 'ffmpeg.exe'):
        p = shutil.which(name)
        if p:
            return p

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    candidates = [
        os.path.join(repo_root, 'ffmpeg', 'ffmpeg'),
        os.path.join(repo_root, 'ffmpeg', 'ffmpeg.exe'),
        os.path.join(repo_root, 'ffmpeg', 'bin', 'ffmpeg'),
        os.path.join(repo_root, 'ffmpeg', 'bin', 'ffmpeg.exe'),
        os.path.join(repo_root, 'bin', 'ffmpeg'),
        os.path.join(repo_root, 'bin', 'ffmpeg.exe'),
        os.path.join(repo_root, 'ffmpeg.exe'),
        os.path.join(repo_root, 'ffmpeg'),
    ]

    user_profile = os.environ.get('USERPROFILE', '')
    local_app_data = os.environ.get('LOCALAPPDATA', '')
    program_files = os.environ.get('ProgramFiles', r'C:\Program Files')
    program_files_x86 = os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')
    windows_candidates = [
        r'C:\ffmpeg\bin\ffmpeg.exe',
        r'C:\ffmpeg\ffmpeg.exe',
        os.path.join(program_files, 'ffmpeg', 'bin', 'ffmpeg.exe'),
        os.path.join(program_files_x86, 'ffmpeg', 'bin', 'ffmpeg.exe'),
        os.path.join(program_files, 'ImageMagick-7.1.1-Q16-HDRI', 'ffmpeg.exe'),
        os.path.join(local_app_data, 'Microsoft', 'WinGet', 'Links', 'ffmpeg.exe'),
        os.path.join(user_profile, 'scoop', 'shims', 'ffmpeg.exe'),
        os.path.join(user_profile, 'scoop', 'apps', 'ffmpeg', 'current', 'bin', 'ffmpeg.exe'),
        os.path.join(os.environ.get('ProgramData', r'C:\ProgramData'), 'chocolatey', 'bin', 'ffmpeg.exe'),
    ]
    candidates.extend(windows_candidates)

    for c in candidates:
        if os.path.isfile(c):
            return c

    try:
        import imageio_ffmpeg
        p = imageio_ffmpeg.get_ffmpeg_exe()
        if p and os.path.isfile(p):
            return p
    except Exception:
        pass

    return None


class ImageFormats:
    formatos_imagen = ['png', 'jpg', 'jpeg', 'webp', 'bmp', 'tiff', 'gif', 'ico']

    @staticmethod
    def _open_image(ruta_origen):
        return Image.open(ruta_origen)

    @staticmethod
    def _save_image(img: Image.Image, ruta_destino: str, formato: str, quality: int = 85):
        ruta_destino = _prepare_dest(ruta_destino)
        formato_lower = formato.lower()

        if formato_lower in ('jpg', 'jpeg'):
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                fondo = Image.new('RGB', img.size, (255, 255, 255))
                fondo.paste(img.convert('RGBA'), mask=img.convert('RGBA').split()[-1])
                fondo.save(ruta_destino, 'JPEG', quality=quality)
            else:
                img.convert('RGB').save(ruta_destino, 'JPEG', quality=quality)
        elif formato_lower == 'png':
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                img.save(ruta_destino, 'PNG', optimize=True)
            else:
                img.convert('RGB').save(ruta_destino, 'PNG', optimize=True)
        elif formato_lower == 'webp':
            img.save(ruta_destino, 'WEBP', quality=quality, method=6)
        elif formato_lower == 'ico':
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            # Ensure it fits max standard ico size, but PIL handles standard resizing or saves as is.
            img.save(ruta_destino, format='ICO')
        else:
            try:
                img.save(ruta_destino, formato.upper())
            except Exception:
                img.save(ruta_destino)

        return f"✅ Convertido: {os.path.basename(ruta_destino)}"

    @staticmethod
    def convertir(ruta_origen, ruta_destino, formato_destino=None):
        try:
            if formato_destino is None:
                formato_destino = os.path.splitext(ruta_destino)[1].lstrip('.').lower()
            img = ImageFormats._open_image(ruta_origen)
            return ImageFormats._save_image(img, ruta_destino, formato_destino)
        except Exception as e:
            return f"⚠️ Error con {os.path.basename(ruta_origen)}: {e}"

    @staticmethod
    def convertir_jpg_a_png(ruta_origen, ruta_destino):
        try:
            img = ImageFormats._open_image(ruta_origen)
            return ImageFormats._save_image(img, ruta_destino, 'png')
        except Exception as e:
            return f"⚠️ Error con {os.path.basename(ruta_origen)}: {e}"

    @staticmethod
    def convertir_jpg_a_webp(ruta_origen, ruta_destino):
        try:
            img = ImageFormats._open_image(ruta_origen)
            return ImageFormats._save_image(img, ruta_destino, 'webp')
        except Exception as e:
            return f"⚠️ Error con {os.path.basename(ruta_origen)}: {e}"

    @staticmethod
    def convertir_png_a_jpg(ruta_origen, ruta_destino):
        try:
            img = ImageFormats._open_image(ruta_origen)
            return ImageFormats._save_image(img, ruta_destino, 'jpg')
        except Exception as e:
            return f"⚠️ Error con {os.path.basename(ruta_origen)}: {e}"

    @staticmethod
    def convertir_png_a_webp(ruta_origen, ruta_destino):
        try:
            img = ImageFormats._open_image(ruta_origen)
            return ImageFormats._save_image(img, ruta_destino, 'webp')
        except Exception as e:
            return f"⚠️ Error con {os.path.basename(ruta_origen)}: {e}"

    @staticmethod
    def convertir_webp_a_jpg(ruta_origen, ruta_destino):
        try:
            img = ImageFormats._open_image(ruta_origen)
            return ImageFormats._save_image(img, ruta_destino, 'jpg')
        except Exception as e:
            return f"⚠️ Error con {os.path.basename(ruta_origen)}: {e}"

    @staticmethod
    def convertir_webp_a_png(ruta_origen, ruta_destino):
        try:
            img = ImageFormats._open_image(ruta_origen)
            return ImageFormats._save_image(img, ruta_destino, 'png')
        except Exception as e:
            return f"⚠️ Error con {os.path.basename(ruta_origen)}: {e}"


class ImageRescalerLogic:
    @staticmethod
    def reescalar_imagen(ruta_origen, ruta_destino, modo="pixeles", ancho_target=None, alto_target=None, porcentaje=None, mantener_aspecto=True, no_agrandar=False):
        try:
            img = Image.open(ruta_origen)
            w, h = img.size

            if modo == "porcentaje":
                if porcentaje is None:
                    return "⚠️ Error: Porcentaje no especificado."
                factor = porcentaje / 100.0
                new_w = int(w * factor)
                new_h = int(h * factor)
            else: # pixeles
                if ancho_target is None or alto_target is None:
                    return "⚠️ Error: Ancho y alto deben especificarse en modo píxeles."
                new_w = int(ancho_target)
                new_h = int(alto_target)

                if mantener_aspecto:
                    # Si mantener aspecto está activo, recalculamos en base a la escala más restrictiva
                    # O podemos simplemente reescalar manteniendo el aspecto del ancho. 
                    # Generalmente se respeta el que se modificó, pero dejaremos que la UI mande 
                    # el ancho/alto con el aspecto ya mantenido o recalculamos acá si hace falta.
                    # Asumimos que la UI ya pasa los valores correctamente ajustados.
                    pass

            if no_agrandar:
                if new_w > w or new_h > h:
                    new_w = min(new_w, w)
                    new_h = min(new_h, h)

            if (new_w, new_h) == (w, h):
                # No resize needed, just save copy
                img_resized = img
            else:
                img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                
            return ImageFormats._save_image(img_resized, ruta_destino, os.path.splitext(ruta_destino)[1].lstrip('.').lower())
        except Exception as e:
            return f"⚠️ Error reescalando {os.path.basename(ruta_origen)}: {e}"


class BackgroundRemoverLogic:
    _LOCK = None
    _SESSION_CACHE = {}

    @classmethod
    def _get_lock(cls):
        if cls._LOCK is None:
            import threading
            cls._LOCK = threading.Lock()
        return cls._LOCK

    @classmethod
    def _ensure_streams(cls):
        import sys
        import io
        if sys.stdout is None:
            sys.stdout = io.StringIO()
        if sys.stderr is None:
            sys.stderr = io.StringIO()

    @classmethod
    def _load_rembg(cls):
        """Carga rembg y toda su cadena de dependencias en orden determinista para evitar
        errores transitorios o circulares de lazy_loader en el primer uso."""
        import sys
        import importlib
        cls._ensure_streams()

        prereq_modules = [
            "numpy",
            "scipy",
            "scipy.ndimage",
            "scipy.spatial",
            "scipy.sparse",
            "scipy.sparse.linalg",
            "skimage",
            "skimage._shared",
            "skimage.util",
            "skimage.measure",
            "skimage.draw",
            "skimage.filters",
            "skimage.morphology",
            "numba",
            "pymatting",
            "onnxruntime",
            "pooch",
        ]

        last_err = None
        for attempt in range(3):
            try:
                for mod_name in prereq_modules:
                    try:
                        importlib.import_module(mod_name)
                    except Exception:
                        pass
                import rembg
                return rembg
            except ImportError as e:
                last_err = e
                # Si estamos en entorno Python no congelado y falta el paquete, intentar instalarlo
                if attempt == 1 and not getattr(sys, "frozen", False):
                    try:
                        import subprocess
                        startupinfo = None
                        if os.name == "nt":
                            startupinfo = subprocess.STARTUPINFO()
                            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        subprocess.run(
                            [sys.executable, "-m", "pip", "install", "rembg[cpu]", "onnxruntime"],
                            check=False,
                            startupinfo=startupinfo,
                            capture_output=True,
                        )
                    except Exception:
                        pass
        if last_err:
            raise last_err
        import rembg
        return rembg

    @classmethod
    def get_session(cls, model_name="u2net"):
        with cls._get_lock():
            cls._ensure_streams()
            rembg = cls._load_rembg()
            if model_name not in cls._SESSION_CACHE:
                cls._SESSION_CACHE[model_name] = rembg.new_session(model_name)
            return rembg, cls._SESSION_CACHE[model_name]

    @classmethod
    def prewarm(cls, model_name="u2net"):
        """Pre-carga rembg y la sesión por defecto en segundo plano al iniciar la app
        para que el primer uso sea inmediato y descargue el modelo si aún no existe."""
        try:
            cls.get_session(model_name)
        except Exception:
            pass

    @staticmethod
    def quitar_fondo(ruta_origen, ruta_destino, model_name="u2net", alpha_matting=False):
        try:
            rembg, session = BackgroundRemoverLogic.get_session(model_name)
            with open(ruta_origen, "rb") as input_file:
                input_data = input_file.read()

            output_data = rembg.remove(
                input_data,
                session=session,
                post_process_mask=True,
                alpha_matting=alpha_matting
            )

            # Ensure the destination path is absolute and exists
            ruta_destino = _prepare_dest(ruta_destino)

            with open(ruta_destino, "wb") as output_file:
                output_file.write(output_data)

            return f"✅ Fondo eliminado: {os.path.basename(ruta_destino)}"
        except Exception as e:
            return f"⚠️ Error quitando fondo a {os.path.basename(ruta_origen)}: {e}"


class ImageEnhancerLogic:
    @staticmethod
    def _download_model_if_needed():
        import requests
        import zipfile
        
        # 1. Buscar primero en la carpeta local del proyecto
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        local_exe = os.path.join(repo_root, 'apps', 'models', 'realesrgan', 'realesrgan-ncnn-vulkan.exe')
        if os.path.isfile(local_exe):
            return local_exe
        
        # 2. Si no existe localmente, descargar a ProgramData para evitar errores de espacios en rutas (bug de _wfopen en realesrgan)
        appdata_dir = os.environ.get('ProgramData')
        if not appdata_dir:
            appdata_dir = os.environ.get('APPDATA') or os.path.expanduser('~')
        models_dir = os.path.join(appdata_dir, "MediaHub", "models", "realesrgan")
        os.makedirs(models_dir, exist_ok=True)
        exe_path = os.path.join(models_dir, "realesrgan-ncnn-vulkan.exe")
        
        if not os.path.exists(exe_path):
            zip_path = os.path.join(models_dir, "realesrgan.zip")
            url = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip"
            response = requests.get(url, stream=True)
            if response.status_code == 200:
                with open(zip_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(models_dir)
                    
                os.remove(zip_path)
            else:
                raise Exception("No se pudo descargar el modelo de Super Resolución (Real-ESRGAN).")
        return exe_path

    @staticmethod
    def mejorar_calidad(ruta_origen, ruta_destino, model_name="realesrgan-x4plus", scale=4, use_tta=False):
        import subprocess
        import tempfile
        import shutil
        import uuid
        try:
            exe_path = ImageEnhancerLogic._download_model_if_needed()
            
            # Ensure the destination path is absolute and exists
            ruta_destino = _prepare_dest(ruta_destino)
            
            # Use temp files to avoid Unicode issues with the executable
            temp_dir = tempfile.gettempdir()
            unique_id = str(uuid.uuid4())
            ext_origen = os.path.splitext(ruta_origen)[1].lower()
            if not ext_origen:
                ext_origen = ".png"
            
            input_tmp = os.path.join(temp_dir, f"input_{unique_id}{ext_origen}")
            output_tmp = os.path.join(temp_dir, f"output_{unique_id}.png")
            
            shutil.copy2(ruta_origen, input_tmp)
            
            # Run Real-ESRGAN
            cmd = [
                exe_path,
                "-i", input_tmp,
                "-o", output_tmp,
                "-s", str(scale),
                "-n", model_name,
                "-t", "400"
            ]
            
            if use_tta:
                cmd.append("-x")
            
            # Hide console window on Windows
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            try:
                subprocess.run(cmd, check=True, startupinfo=startupinfo, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                raise Exception(f"El motor de IA falló: {e.stderr.strip() if e.stderr else str(e)}")
            
            if os.path.exists(output_tmp):
                shutil.copy2(output_tmp, ruta_destino)
            else:
                raise Exception("El programa no generó la imagen de salida.")
                
            # Cleanup
            try:
                os.remove(input_tmp)
                os.remove(output_tmp)
            except:
                pass
            
            return f"✅ Calidad mejorada con IA (Real-ESRGAN): {os.path.basename(ruta_destino)}"
        except Exception as e:
            return f"⚠️ Error mejorando la calidad de {os.path.basename(ruta_origen)}: {e}"


class AudioFormats:
    formatos_audio = ['mp3', 'wav', 'flac', 'ogg', 'm4a', 'mpeg', 'aac', 'wma', 'alac', 'aiff']

    @staticmethod
    def _run_ffmpeg(ruta_origen, ruta_destino, extra_args=None):
        import subprocess
        if extra_args is None:
            extra_args = []
        ruta_destino = _prepare_dest(ruta_destino)
        ffmpeg_path = _find_ffmpeg()
        if not ffmpeg_path:
            return False, '❌ ffmpeg no está disponible. Añádelo a PATH o define la variable de entorno FFMPEG_PATH apuntando al ejecutable.'
        cmd = [ffmpeg_path, '-y', '-i', ruta_origen] + extra_args + [ruta_destino]
        try:
            repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, cwd=repo_root)
            return True, f"✅ Convertido: {os.path.basename(ruta_origen)} -> {os.path.basename(ruta_destino)}"
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode(errors='replace') if isinstance(e.stderr, (bytes, bytearray)) else str(e.stderr)
            return False, f"⚠️ Error en ffmpeg: {stderr}"

    @staticmethod
    def _default_audio_args(formato_destino: str):
        fmt = (formato_destino or '').lower()
        if fmt == 'mp3':
            return ['-vn', '-c:a', 'libmp3lame', '-b:a', '192k']
        if fmt == 'wav':
            return ['-vn', '-c:a', 'pcm_s16le', '-ar', '44100', '-ac', '2']
        if fmt == 'flac':
            return ['-vn', '-c:a', 'flac']
        if fmt == 'ogg':
            return ['-vn', '-c:a', 'libvorbis', '-q:a', '5']
        if fmt in ('m4a', 'aac'):
            return ['-vn', '-c:a', 'aac', '-b:a', '192k']
        return ['-vn', '-c:a', 'aac', '-b:a', '192k']

    @staticmethod
    def convertir(ruta_origen, ruta_destino, formato_destino=None):
        try:
            if formato_destino is None:
                formato_destino = os.path.splitext(ruta_destino)[1].lstrip('.').lower()
            extra_args = AudioFormats._default_audio_args(formato_destino)
            ok, msg = AudioFormats._run_ffmpeg(ruta_origen, ruta_destino, extra_args=extra_args)
            return msg
        except Exception as e:
            return f"⚠️ Error con {os.path.basename(ruta_origen)}: {e}"


class VideoFormats:
    formatos_video = ['mp4', 'mkv', 'avi', 'mov', 'webm', 'flv', 'wmv', 'm4v', '3gp', 'mpeg', 'mp3']

    @staticmethod
    def _run_ffmpeg(ruta_origen, ruta_destino, extra_args=None):
        import subprocess
        if extra_args is None:
            extra_args = []
        ruta_destino = _prepare_dest(ruta_destino)
        ffmpeg_path = _find_ffmpeg()
        if not ffmpeg_path:
            return False, '❌ ffmpeg no está disponible. Añádelo a PATH o define la variable de entorno FFMPEG_PATH apuntando al ejecutable.'
        cmd = [ffmpeg_path, '-y', '-i', ruta_origen] + extra_args + [ruta_destino]
        try:
            repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, cwd=repo_root)
            return True, f"✅ Convertido: {os.path.basename(ruta_origen)} -> {os.path.basename(ruta_destino)}"
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode(errors='replace') if isinstance(e.stderr, (bytes, bytearray)) else str(e.stderr)
            return False, f"⚠️ Error en ffmpeg: {stderr}"

    _hw_encoder = None

    @classmethod
    def get_hw_encoder(cls):
        if cls._hw_encoder is not None:
            return cls._hw_encoder
            
        cls._hw_encoder = "libx264" # default fallback
        import subprocess, os
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            r = subprocess.run(['wmic', 'path', 'win32_VideoController', 'get', 'name'], capture_output=True, text=True, startupinfo=startupinfo)
            out = r.stdout.lower()
            if "nvidia" in out:
                cls._hw_encoder = "h264_nvenc"
            elif "amd" in out or "radeon" in out:
                cls._hw_encoder = "h264_amf"
        except:
            pass
        return cls._hw_encoder

    @staticmethod
    def _default_video_args(formato_destino: str):
        fmt = (formato_destino or '').lower()
        hw = VideoFormats.get_hw_encoder()
        
        if fmt in ('mp4', 'mov', 'm4v'):
            return ['-c:v', hw, '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart']
        if fmt == 'mkv':
            return ['-c:v', hw, '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k']
        if fmt == 'webm':
            return ['-c:v', 'libvpx-vp9', '-b:v', '0', '-crf', '32', '-c:a', 'libopus', '-b:a', '128k']
        if fmt == 'avi':
            return ['-c:v', 'mpeg4', '-q:v', '5', '-c:a', 'libmp3lame', '-b:a', '192k']
        if fmt == 'wmv':
            return ['-c:v', 'wmv2', '-c:a', 'wmav2']
        if fmt == 'flv':
            return ['-c:v', 'flv', '-c:a', 'libmp3lame', '-b:a', '128k']
        if fmt == '3gp':
            return ['-c:v', 'h263', '-c:a', 'aac', '-b:a', '96k']
        if fmt == 'mp3':
            # Extraer solo el audio en mp3 (descartar video)
            return ['-vn', '-c:a', 'libmp3lame', '-b:a', '192k']
        return ['-c:v', hw, '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k']

    @staticmethod
    def convertir(ruta_origen, ruta_destino, formato_destino=None):
        try:
            if formato_destino is None:
                formato_destino = os.path.splitext(ruta_destino)[1].lstrip('.').lower()
            extra_args = VideoFormats._default_video_args(formato_destino)
            ok, msg = VideoFormats._run_ffmpeg(ruta_origen, ruta_destino, extra_args=extra_args)
            return msg
        except Exception as e:
            return f"⚠️ Error con {os.path.basename(ruta_origen)}: {e}"

class SubtitleGeneratorLogic:
    @staticmethod
    def _download_whisper_if_needed():
        import requests, zipfile, os
        appdata_dir = os.environ.get('ProgramData')
        if not appdata_dir:
            appdata_dir = os.environ.get('APPDATA') or os.path.expanduser('~')
        whisper_dir = os.path.join(appdata_dir, "MediaHub", "models", "whisper")
        os.makedirs(whisper_dir, exist_ok=True)
        exe_path = os.path.join(whisper_dir, "main.exe")
        
        if not os.path.exists(exe_path):
            zip_path = os.path.join(whisper_dir, "whisper-bin-x64.zip")
            url = "https://github.com/ggerganov/whisper.cpp/releases/download/v1.5.4/whisper-bin-x64.zip"
            response = requests.get(url, stream=True)
            if response.status_code == 200:
                with open(zip_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(whisper_dir)
                os.remove(zip_path)
            else:
                raise Exception("No se pudo descargar el motor Whisper.")
        return exe_path

    @staticmethod
    def _download_model_if_needed(model_size):
        import requests, os
        appdata_dir = os.environ.get('ProgramData')
        if not appdata_dir:
            appdata_dir = os.environ.get('APPDATA') or os.path.expanduser('~')
        models_dir = os.path.join(appdata_dir, "MediaHub", "models", "whisper")
        os.makedirs(models_dir, exist_ok=True)
        
        model_name = f"ggml-{model_size}.bin"
        model_path = os.path.join(models_dir, model_name)
        
        if not os.path.exists(model_path):
            url = f"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/{model_name}"
            response = requests.get(url, stream=True)
            if response.status_code == 200:
                with open(model_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
            else:
                raise Exception(f"No se pudo descargar el modelo {model_size}.")
        return model_path

    @staticmethod
    def generar_subtitulos(ruta_origen, ruta_destino, model_size="tiny", language="auto"):
        import subprocess, tempfile, os, shutil, uuid
        try:
            exe_path = SubtitleGeneratorLogic._download_whisper_if_needed()
            model_path = SubtitleGeneratorLogic._download_model_if_needed(model_size)
            
            ruta_destino = _prepare_dest(ruta_destino)
            temp_dir = tempfile.gettempdir()
            unique_id = str(uuid.uuid4())
            wav_tmp = os.path.join(temp_dir, f"audio_{unique_id}.wav")
            
            # Extract 16kHz wav audio
            ffmpeg_path = _find_ffmpeg()
            if not ffmpeg_path:
                return "❌ ffmpeg no está disponible."
            
            cmd_ffmpeg = [ffmpeg_path, "-y", "-i", ruta_origen, "-vn", "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav_tmp]
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            subprocess.run(cmd_ffmpeg, check=True, startupinfo=startupinfo, capture_output=True)
            
            # Run Whisper
            cmd_whisper = [
                exe_path,
                "-m", model_path,
                "-f", wav_tmp,
                "-l", language,
                "-osrt"
            ]
            
            res = subprocess.run(cmd_whisper, check=False, startupinfo=startupinfo, capture_output=True, text=True)
            if res.returncode != 0:
                raise Exception(f"Whisper falló: {res.stderr}")
            
            srt_tmp = wav_tmp + ".srt"
            if os.path.exists(srt_tmp):
                shutil.copy2(srt_tmp, ruta_destino)
                os.remove(srt_tmp)
            else:
                raise Exception("El programa no generó el archivo SRT.")
            
            if os.path.exists(wav_tmp):
                os.remove(wav_tmp)
                
            return f"✅ Subtítulos generados: {os.path.basename(ruta_destino)}"
        except Exception as e:
            return f"⚠️ Error generando subtítulos: {e}"

class WatermarkLogic:
    @staticmethod
    def _parse_rgb_color(color_val):
        if isinstance(color_val, (tuple, list)) and len(color_val) >= 3:
            return int(color_val[0]), int(color_val[1]), int(color_val[2])
        if isinstance(color_val, str):
            c = color_val.strip().lstrip("#")
            if len(c) == 6:
                try:
                    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
                except Exception:
                    pass
        return 255, 255, 255

    @staticmethod
    def render_watermark_pil(base_image, params: dict):
        """Renderiza marca de agua avanzada (texto o logo) con soporte para:
        - Color de texto personalizado
        - Tamaño de letra / escala
        - Espaciado entre letras (letter_spacing)
        - Separación entre repeticiones (separation)
        - Dirección / Ángulo de rotación (angle)
        - Modos: 'xy' (coordenadas X-Y ajustables 0-100%), 'mosaic_diag', 'mosaic_horiz', 'mosaic_vert'
        """
        from PIL import Image, ImageDraw, ImageFont

        base_rgba = base_image.convert("RGBA")
        w, h = base_rgba.size
        if w <= 0 or h <= 0:
            return base_rgba

        scale_factor = max(w, h) / 1000.0
        wm_type = params.get("wm_type", "texto")
        text = params.get("text", "Media Hub") or "Media Hub"
        logo = params.get("logo", None)
        opac = max(5, min(100, int(params.get("opacity", 70))))
        font_size_param = max(8, int(params.get("font_size", 40)))
        letter_spacing_param = max(0, int(params.get("letter_spacing", 0)))
        separation_param = max(15, int(params.get("separation", 120)))
        mode = params.get("mode", "xy")
        pos_x = max(0, min(100, int(params.get("pos_x", 50))))
        pos_y = max(0, min(100, int(params.get("pos_y", 50))))
        angle = int(params.get("angle", 0))
        r, g, b = WatermarkLogic._parse_rgb_color(params.get("color", "#FFFFFF"))

        # 1. Construir estampa individual (stamp)
        if wm_type == "imagen" and logo and os.path.exists(logo):
            stamp = Image.open(logo).convert("RGBA")
            if opac < 100:
                alpha_ch = stamp.split()[3].point(lambda p: int(p * (opac / 100.0)))
                stamp.putalpha(alpha_ch)
            wm_ratio = max(0.05, stamp.width / max(1, stamp.height))
            new_w = max(16, int(w * (font_size_param / 220.0)))
            new_h = max(16, int(new_w / wm_ratio))
            stamp = stamp.resize((new_w, new_h), Image.Resampling.LANCZOS)
        else:
            actual_font_size = max(10, int(font_size_param * scale_factor))
            font = None
            for font_candidate in ("arialbd.ttf", "arial.ttf", "segoeuib.ttf", "segoeui.ttf"):
                try:
                    font = ImageFont.truetype(font_candidate, actual_font_size)
                    break
                except Exception:
                    continue
            if font is None:
                font = ImageFont.load_default()

            actual_spacing = int(letter_spacing_param * scale_factor)
            dummy = Image.new("RGBA", (1, 1))
            d_dummy = ImageDraw.Draw(dummy)

            char_widths = []
            max_top = 0
            max_bottom = actual_font_size
            for idx, ch in enumerate(text):
                bbox = d_dummy.textbbox((0, 0), ch, font=font)
                cw = max(1, int(d_dummy.textlength(ch, font=font)))
                char_widths.append(cw)
                if idx == 0 or bbox[1] < max_top:
                    max_top = bbox[1]
                if bbox[3] > max_bottom:
                    max_bottom = bbox[3]

            tw = sum(char_widths) + actual_spacing * max(0, len(text) - 1)
            th = max(actual_font_size, max_bottom - max_top)
            pad = max(6, int(actual_font_size * 0.35))

            stamp = Image.new("RGBA", (max(1, tw + pad * 2), max(1, th + pad * 2)), (0, 0, 0, 0))
            d_stamp = ImageDraw.Draw(stamp)
            alpha_val = int(255 * (opac / 100.0))

            cur_x = pad
            draw_y = pad - max_top
            for ch, cw in zip(text, char_widths):
                d_stamp.text((cur_x, draw_y), ch, fill=(r, g, b, alpha_val), font=font)
                cur_x += cw + actual_spacing

        # 2. Aplicar rotación según modo y ángulo
        rot_angle = angle
        if mode == "mosaic_diag" and angle == 0:
            rot_angle = 35
        elif mode == "mosaic_vert" and angle == 0:
            rot_angle = 90

        if rot_angle != 0:
            stamp = stamp.rotate(rot_angle, expand=True, resample=Image.Resampling.BICUBIC)

        # 3. Componer capa de marca de agua según el modo
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        sw, sh = stamp.size

        if mode == "xy":
            x = int((w - sw) * (pos_x / 100.0))
            y = int((h - sh) * (pos_y / 100.0))
            layer.paste(stamp, (x, y), stamp)
        else:
            gap = max(12, int(separation_param * scale_factor))
            step_x = max(16, sw + gap)
            step_y = max(16, sh + gap)

            row_idx = 0
            for y in range(-sh, h + sh, step_y):
                x_offset = (step_x // 2) if (mode == "mosaic_diag" and row_idx % 2 == 1) else 0
                col_idx = 0
                for x in range(-sw + x_offset, w + sw, step_x):
                    y_offset = (step_y // 2) if (mode == "mosaic_vert" and col_idx % 2 == 1) else 0
                    layer.paste(stamp, (x, y + y_offset), stamp)
                    col_idx += 1
                row_idx += 1

        return Image.alpha_composite(base_rgba, layer)

    @staticmethod
    def aplicar_marca_agua(ruta_origen, ruta_destino, watermark_path, position="bottom-right", opacity=100):
        import os
        try:
            ruta_destino = _prepare_dest(ruta_destino)
            ext = os.path.splitext(ruta_origen)[1].lower()
            
            if ext in ['.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv']:
                return WatermarkLogic._watermark_video(ruta_origen, ruta_destino, watermark_path, position, opacity)
            else:
                return WatermarkLogic._watermark_image(ruta_origen, ruta_destino, watermark_path, position, opacity)
        except Exception as e:
            return f"⚠️ Error aplicando marca de agua: {e}"

    @staticmethod
    def _watermark_image(ruta_origen, ruta_destino, watermark_path, position, opacity):
        from PIL import Image
        import os
        base_image = Image.open(ruta_origen).convert("RGBA")
        watermark = Image.open(watermark_path).convert("RGBA")
        
        if opacity < 100:
            alpha = watermark.split()[3]
            alpha = alpha.point(lambda p: p * (opacity / 100.0))
            watermark.putalpha(alpha)
            
        wm_ratio = watermark.width / watermark.height
        new_wm_width = int(base_image.width * 0.15)
        new_wm_height = int(new_wm_width / wm_ratio)
        watermark = watermark.resize((new_wm_width, new_wm_height), Image.Resampling.LANCZOS)
        
        margin = int(base_image.width * 0.03)
        x, y = 0, 0
        if position == "top-left":
            x, y = margin, margin
        elif position == "top-right":
            x, y = base_image.width - watermark.width - margin, margin
        elif position == "bottom-left":
            x, y = margin, base_image.height - watermark.height - margin
        elif position == "bottom-right":
            x, y = base_image.width - watermark.width - margin, base_image.height - watermark.height - margin
        elif position == "center":
            x, y = (base_image.width - watermark.width) // 2, (base_image.height - watermark.height) // 2
            
        base_image.paste(watermark, (x, y), watermark)
        
        formato = os.path.splitext(ruta_destino)[1].lstrip('.').lower()
        if formato in ['jpg', 'jpeg']:
            base_image = base_image.convert("RGB")
            base_image.save(ruta_destino, quality=95)
        else:
            base_image.save(ruta_destino)
            
        return f"✅ Marca de agua aplicada: {os.path.basename(ruta_destino)}"

    @staticmethod
    def _watermark_video(ruta_origen, ruta_destino, watermark_path, position, opacity):
        import subprocess, os
        ffmpeg_path = _find_ffmpeg()
        if not ffmpeg_path:
            return "❌ ffmpeg no está disponible."
            
        margin_expr = "main_w*0.03"
        if position == "top-left":
            overlay = f"overlay={margin_expr}:{margin_expr}"
        elif position == "top-right":
            overlay = f"overlay=main_w-overlay_w-{margin_expr}:{margin_expr}"
        elif position == "bottom-left":
            overlay = f"overlay={margin_expr}:main_h-overlay_h-{margin_expr}"
        elif position == "bottom-right":
            overlay = f"overlay=main_w-overlay_w-{margin_expr}:main_h-overlay_h-{margin_expr}"
        elif position == "center":
            overlay = "overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2"
            
        opc = opacity / 100.0
        
        filter_complex = f"[1:v]format=rgba,colorchannelmixer=aa={opc}[wm];[0:v][wm]{overlay}"
        
        cmd = [
            ffmpeg_path, "-y",
            "-i", ruta_origen,
            "-i", watermark_path,
            "-filter_complex", filter_complex,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "copy",
            ruta_destino
        ]
        
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        try:
            subprocess.run(cmd, check=True, startupinfo=startupinfo, capture_output=True, text=True)
            return f"✅ Marca de agua aplicada: {os.path.basename(ruta_destino)}"
        except subprocess.CalledProcessError as e:
            return f"⚠️ Error en FFmpeg: {e.stderr}"
