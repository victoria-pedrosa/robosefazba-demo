import sys
import os
import time
import shutil
import pandas as pd
from io import BytesIO
from PIL import Image
import pytesseract
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv
load_dotenv()  # lê o .env local (não vai para o GitHub)

# =======================================================
# O "GPS" DO ROBÔ (GARANTE QUE ELE OLHE A PASTA CERTA)
# =======================================================
if getattr(sys, 'frozen', False):
    # Se estiver rodando como .exe
    DIRETORIO_ATUAL = os.path.dirname(sys.executable)
else:
    # Se estiver rodando no VS Code como .py
    DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))

# =======================================================
# 1. CONFIGURAÇÕES INICIAIS E NOMES DAS COLUNAS
# =======================================================
NOME_PLANILHA = os.path.join(DIRETORIO_ATUAL, 'planilha_sefaz.xlsx')
PLANILHA_SAIDA = os.path.join(DIRETORIO_ATUAL, 'planilha_sefaz_atualizada.xlsx')
NOME_DA_ABA = '022026'

COL_CODIGO = 'CÓDIGO'             
COL_FILIAL = 'TIPO'               
COL_DT_INI = 'DATA INICIAL'       
COL_DT_FIN = 'DATA FINAL'         

# =======================================================
# CONFIGURAÇÃO DO LEITOR (TESSERACT) E CHROME
# =======================================================
pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_CMD", r'C:\Program Files\Tesseract-OCR\tesseract.exe')

PASTA_DOWNLOADS_TEMP = os.path.join(DIRETORIO_ATUAL, 'downloads_temp')
if not os.path.exists(PASTA_DOWNLOADS_TEMP):
    os.makedirs(PASTA_DOWNLOADS_TEMP)

chrome_options = Options()
chrome_options.add_argument('--ignore-certificate-errors')
chrome_options.add_argument('--safebrowsing-disable-download-protection')
prefs = {"download.default_directory": PASTA_DOWNLOADS_TEMP,
         "download.prompt_for_download": False,
         "directory_upgrade": True,
         "safebrowsing.enabled": False}
chrome_options.add_experimental_option("prefs", prefs)

df = pd.read_excel(NOME_PLANILHA, sheet_name=NOME_DA_ABA, dtype=str)

url_entrada = "https://nfe.sefaz.ba.gov.br/servicos/NFENC/SSL/ASLibrary/Login?ReturnUrl=%2fservicos%2fnfenc%2fModulos%2fAutenticado%2fRestrito%2fNFENC_consulta_destinatario.aspx"
url_saida = "https://nfe.sefaz.ba.gov.br/servicos/NFENC/SSL/ASLibrary/Login?ReturnUrl=%2fservicos%2fnfenc%2fModulos%2fAutenticado%2fRestrito%2fNFENC_consulta_emitente.aspx"

def processar_notas(driver, url, login, senha, caminho_salvar, tipo, dt_ini_limpa, dt_fin_limpa, codigo_emp, filial_emp):
    driver.get(url)
    wait = WebDriverWait(driver, 10)
    
    try:
        # 1. FAZ O LOGIN
        wait.until(EC.presence_of_element_located((By.ID, 'PHCentro_userLogin'))).send_keys(login)
        campo_senha = driver.find_element(By.ID, 'PHCentro_userPass')
        campo_senha.send_keys(senha)
        campo_senha.send_keys(Keys.ENTER)
        
        # 2. PREENCHE AS DATAS DA PLANILHA
        wait.until(EC.presence_of_element_located((By.ID, 'rbt_filtro3'))).click()
        
        campo_dt_ini = driver.find_element(By.ID, 'txtPeriodoInicial')
        campo_dt_ini.send_keys(Keys.CONTROL + "a")
        campo_dt_ini.send_keys(Keys.DELETE)
        campo_dt_ini.send_keys(dt_ini_limpa) 
        
        campo_hr_ini = driver.find_element(By.ID, 'txtPeriodoInicialHora')
        campo_hr_ini.send_keys(Keys.CONTROL + "a")
        campo_hr_ini.send_keys(Keys.DELETE)
        campo_hr_ini.send_keys("0000") 
        
        campo_dt_fin = driver.find_element(By.ID, 'txtPeriodoFinal')
        campo_dt_fin.send_keys(Keys.CONTROL + "a")
        campo_dt_fin.send_keys(Keys.DELETE)
        campo_dt_fin.send_keys(dt_fin_limpa)
        
        campo_hr_fin = driver.find_element(By.ID, 'txtPeriodoFinalHora')
        campo_hr_fin.send_keys(Keys.CONTROL + "a")
        campo_hr_fin.send_keys(Keys.DELETE)
        campo_hr_fin.send_keys("2359")
        
        # 3. QUEBRANDO O CAPTCHA
        print(f"[{tipo}] Lendo o Captcha...")
        sucesso_captcha = False
        
        for tentativa in range(10): 
            try:
                img_element = wait.until(EC.presence_of_element_located((By.ID, 'img_captcha')))
                img_png = img_element.screenshot_as_png
                imagem = Image.open(BytesIO(img_png))
                
                texto_ocr = pytesseract.image_to_string(imagem, config='--psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789').strip()
                texto_ocr = texto_ocr.replace(" ", "")
                
                if len(texto_ocr) != 4:
                    print(f"   -> Tentativa {tentativa+1}: Leu '{texto_ocr}' (Tamanho errado. Forçando novo captcha...)")
                    texto_ocr = "ERRO"
                else:
                    print(f"   -> Tentativa {tentativa+1}: Leu '{texto_ocr}'")
                
                campo_captcha = driver.find_element(By.ID, 'txt_cod_antirobo')
                campo_captcha.clear()
                campo_captcha.send_keys(texto_ocr)
                
                driver.find_element(By.ID, 'AplicarFiltro').click()
                time.sleep(2) 
                
                try:
                    alert = driver.switch_to.alert
                    alert.accept()
                    time.sleep(1)
                    continue 
                except:
                    sucesso_captcha = True
                    break
            except Exception:
                time.sleep(1)
                continue
                
        if not sucesso_captcha:
            print(f"[{tipo}] Falha no Captcha após 10 tentativas. Pulando empresa...")
            return "ERRO"
            
        print(f"[{tipo}] CAPTCHA ACERTOU! Verificando dados...")
        
        # 4. BAIXA E RENOMEIA A PLANILHA
        try:
            for f in os.listdir(PASTA_DOWNLOADS_TEMP):
                try:
                    os.remove(os.path.join(PASTA_DOWNLOADS_TEMP, f))
                except:
                    pass 

            btn_gerar = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, 'btn_GerarPlanilha')))
            btn_gerar.click()
            print(f"[{tipo}] Tem notas! Baixando arquivo...")
            
            arquivo_baixado = None
            for _ in range(20):
                arquivos = os.listdir(PASTA_DOWNLOADS_TEMP)
                csv_files = [f for f in arquivos if f.lower().endswith('.csv') and not f.endswith('.crdownload')]
                
                if csv_files:
                    arquivo_baixado = csv_files[0]
                    time.sleep(1.5)
                    break
                time.sleep(1)

            if arquivo_baixado:
                nome_base, extensao = os.path.splitext(arquivo_baixado)
                novo_nome = f"{nome_base}_{codigo_emp}_{filial_emp}{extensao}"
                
                caminho_origem = os.path.join(PASTA_DOWNLOADS_TEMP, arquivo_baixado)
                
                if not os.path.exists(caminho_salvar):
                    os.makedirs(caminho_salvar)
                    
                caminho_destino = os.path.join(caminho_salvar, novo_nome)
                shutil.move(caminho_origem, caminho_destino)
                return "SIM"
            else:
                print(f"[{tipo}] Erro: Demorou muito para baixar o arquivo.")
                return "ERRO" 
            
        except:
            print(f"[{tipo}] Nenhuma nota encontrada no período.")
            return "SEM DADOS"

    except Exception as e:
        print(f"Erro inesperado: {e}")
        return "ERRO"

# =======================================================
# FUNÇÃO BLINDADA PARA FORMATAR DATAS
# =======================================================
def forcar_data_brasil(data_bruta):
    data_str = str(data_bruta).strip()
    if '-' in data_str:
        p = data_str.split(' ')[0].split('-')
        if len(p) == 3: return f"{p[2]:0>2}{p[1]:0>2}{p[0]}"
    elif '/' in data_str:
        p = data_str.split(' ')[0].split('/')
        if len(p) == 3:
            if len(p[0]) == 4: return f"{p[2]:0>2}{p[1]:0>2}{p[0]}"
            else: return f"{p[0]:0>2}{p[1]:0>2}{p[2]}"
    return ''.join(filter(str.isdigit, data_str))[:8]


# =======================================================
# LIGA O MOTOR DO ROBÔ
# =======================================================
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

for index, row in df.iterrows():
    login = str(row['LOGIN']).strip()
    senha = str(row['SENHA']).strip()
    caminho_salvar = str(row['Caminho_Salvar']).strip()
    
    codigo = str(row[COL_CODIGO]).strip()
    filial = str(row[COL_FILIAL]).strip()
    
    dt_ini_limpa = forcar_data_brasil(row[COL_DT_INI])
    dt_fin_limpa = forcar_data_brasil(row[COL_DT_FIN])
    
    print(f"\n======================================")
    print(f"Iniciando: {login} - {filial}")
    print(f"Data Processada pelo Robô: {dt_ini_limpa} a {dt_fin_limpa}")
    print(f"======================================")
    
    status_entrada = processar_notas(driver, url_entrada, login, senha, caminho_salvar, "ENTRADA", dt_ini_limpa, dt_fin_limpa, codigo, filial)
    df.at[index, 'ENTRADA'] = status_entrada
    
    status_saida = processar_notas(driver, url_saida, login, senha, caminho_salvar, "SAIDA", dt_ini_limpa, dt_fin_limpa, codigo, filial)
    df.at[index, 'SAIDA'] = status_saida
    
    if status_entrada in ["SIM", "SEM DADOS"] and status_saida in ["SIM", "SEM DADOS"]:
        df.at[index, 'Status_Captura'] = "OK"
    else:
        df.at[index, 'Status_Captura'] = "ERRO"

driver.quit()
df.to_excel(PLANILHA_SAIDA, index=False, sheet_name=NOME_DA_ABA)
print("\nProcesso Finalizado! Verifique a sua planilha atualizada.")