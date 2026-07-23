import sys

def test_gemini_key(api_key):
    print(f"Probando la API Key: {api_key[:5]}...{api_key[-5:]}")
    try:
        from google import genai
        from google.genai import types
        
        client = genai.Client(api_key=api_key)
        
        # Intentar una consulta básica
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Hola, ¿estás ahí?"
        )
        print("\n[ÉXITO] La API Key es válida. Respuesta del modelo:")
        print(resp.text)
        return True
    except Exception as e:
        err_str = str(e)
        print("\n[ERROR] Falló la conexión con Google Gemini:")
        if "401" in err_str or "UNAUTHENTICATED" in err_str:
            print("❌ La clave de API es inválida, caducó o no tiene permisos. Verifica que esté bien copiada.")
        elif "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
            print("⏳ Has agotado la cuota gratuita temporalmente. Por favor, espera unos minutos e inténtalo de nuevo.")
        else:
            print(f"⚠️ Ocurrió un error inesperado: {err_str[:150]}...")
        return False

if __name__ == "__main__":
    import config
    key = config.GOOGLE_API_KEY
    if not key:
        print("[ERROR] No se encontró la variable GOOGLE_API_KEY en el archivo .env")
    else:
        test_gemini_key(key)
