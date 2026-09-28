import os
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from dotenv import load_dotenv
load_dotenv()  # lê o .env local (não vai para o GitHub)

# --- CONFIGURAÇÕES DE CAMINHOS ---
CAMINHO_PLANILHA = "planilha_sefaz.xlsx - 022026.csv"  # Ajuste conforme o nome exato do arquivo
PASTA_RAIZ_DESTINO = os.getenv("PASTA_RAIZ_DESTINO")
PASTA_DOWNLOAD_TEMPORARIA = os.path.join(os.path.expanduser("~"), "Downloads")

# --- CONFIGURAÇÃO DO SELENIUM ---
options = webdriver.ChromeOptions()
prefs = {
    "download.default_directory": PASTA_DOWNLOAD_TEMPORARIA,
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "plugins.always_open_pdf_externally": True, # Baixa o PDF direto
    "profile.default_content_setting_values.popups": 1 # Permite pop-ups (essencial para o botão bt_dam)
}
options.add_experimental_option("prefs", prefs)

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 15)

def resolver_captcha_direto_do_html():
    """
    Lê o atributo 'alt' de cada tag <img> do captcha, conforme visto na inspeção.
    """
    try:
        # Busca todas as imagens que o src contenha a palavra 'captcha'
        imagens_captcha = driver.find_elements(By.XPATH, "//img[contains(@src, 'captcha')]")
        
        # Extrai a letra do atributo 'alt' e junta tudo em uma string
        texto_captcha = "".join([img.get_attribute("alt") for img in imagens_captcha if img.get_attribute("alt")])
        return texto_captcha.strip()
    except Exception as e:
        print(f"Erro ao extrair texto do captcha: {e}")
        return ""

def processar_empresa(nome_empresa, inscricao_municipal, codigo_dominio):
    print(f"\nIniciando: {nome_empresa} (CGA: {inscricao_municipal})")
    
    pasta_empresa = os.path.join(PASTA_RAIZ_DESTINO, str(nome_empresa).strip())
    os.makedirs(pasta_empresa, exist_ok=True)
    
    driver.get("https://www2.sefaz.salvador.ba.gov.br/servico/2-via-tff-tll")
    
    # --- PREENCHIMENTO DA TELA INICIAL ---
    # Pelos prints, tanto o CGA quanto o Captcha usam a classe "text"
    inputs_texto = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "input.text")))
    
    campo_cga = inputs_texto[0] # O primeiro input.text da tela é o CGA
    campo_cga.clear()
    campo_cga.send_keys(str(inscricao_municipal))
    
    captcha_resolvido = resolver_captcha_direto_do_html()
    print(f"Captcha identificado: {captcha_resolvido}")
    
    campo_captcha = inputs_texto[1] # O segundo input.text da tela é o Captcha
    campo_captcha.clear()
    campo_captcha.send_keys(captcha_resolvido)
    
    # Clicar em Consultar (classe vista no print: submitconsultar)
    botao_consultar = driver.find_element(By.CSS_SELECTOR, "input.submitconsultar")
    botao_consultar.click()
    
    # --- TELA DE EMISSÃO DE COTAS ---
    time.sleep(3) 
    janela_principal = driver.current_window_handle
    
    cotas_para_baixar = {
        "0": f"TFF 2026_COTA UNICA_{codigo_dominio}.pdf",
        "1": f"TFF 2026_COTA 1_{codigo_dominio}.pdf",
        "2": f"TFF 2026_COTA 2_{codigo_dominio}.pdf",
        "3": f"TFF 2026_COTA 3_{codigo_dominio}.pdf"
    }
    
    # Aguarda o select carregar (ID visto no print: opcCotas)
    select_element = wait.until(EC.presence_of_element_located((By.ID, "opcCotas")))
    select = Select(select_element)
    
    for valor_opcao, nome_final_pdf in cotas_para_baixar.items():
        try:
            select.select_by_value(valor_opcao)
            time.sleep(1) # Aguarda a função javascript:verifica_vencimento() processar
            
            arquivos_antes = set(os.listdir(PASTA_DOWNLOAD_TEMPORARIA))
            
            # Clica no botão de imprimir o DAM (ID visto no print: bt_dam)
            botao_imprimir = driver.find_element(By.ID, "bt_dam")
            botao_imprimir.click()
            
            # Monitora o download do arquivo
            download_concluido = False
            for _ in range(15):
                time.sleep(1)
                arquivos_depois = set(os.listdir(PASTA_DOWNLOAD_TEMPORARIA))
                novos_arquivos = arquivos_depois - arquivos_antes
                
                pdf_baixado = [f for f in novos_arquivos if f.lower().endswith('.pdf') and not f.endswith('.crdownload')]
                if pdf_baixado:
                    arquivo_original = os.path.join(PASTA_DOWNLOAD_TEMPORARIA, pdf_baixado[0])
                    arquivo_destino = os.path.join(pasta_empresa, nome_final_pdf)
                    
                    os.rename(arquivo_original, arquivo_destino)
                    print(f"Sucesso: {nome_final_pdf} salvo.")
                    download_concluido = True
                    break
            
            if not download_concluido:
                print(f"Aviso: Tempo limite esgotado para baixar a cota {valor_opcao}")
            
            # Limpeza de pop-ups: se o botão abriu uma guia nova e ela ficou aberta, fecha e volta
            for handle in driver.window_handles:
                if handle != janela_principal:
                    driver.switch_to.window(handle)
                    driver.close()
            driver.switch_to.window(janela_principal)
                
        except Exception as e:
            print(f"Erro ao processar a opção de cota {valor_opcao}: {e}")

# --- EXECUÇÃO PRINCIPAL ---
try:
    # Como a extensão é .csv, use read_csv. Se der erro de formatação (padrão Brasil), mude para sep=';'
    try:
        df = pd.read_csv(CAMINHO_PLANILHA)
    except:
        df = pd.read_csv(CAMINHO_PLANILHA, sep=';', encoding='latin1')
    
    for index, row in df.iterrows():
        # Captura os dados baseado na sua estrutura (ajuste os nomes exatos das colunas se precisar)
        nome_empresa = row.iloc[0] # Assumindo Empresa na Coluna A (Índice 0)
        inscricao_municipal = row.iloc[4] # Coluna E (Índice 4) é a 5ª coluna
        codigo_dominio = row['LOGIN'] # Altere para o nome correto do cabeçalho de login/código
        
        if pd.isna(nome_empresa) or pd.isna(inscricao_municipal):
            continue
            
        try:
            # Formata a Inscrição para garantir que seja apenas o número antes de eventuais pontos
            cga_limpo = str(inscricao_municipal).split('.')[0]
            processar_empresa(nome_empresa, cga_limpo, codigo_dominio)
        except Exception as e:
            print(f"Erro crítico ao processar empresa {nome_empresa}: {e}")
            
finally:
    driver.quit()
    print("\nProcesso finalizado.")
