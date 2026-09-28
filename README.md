# Robosefazba

> Projeto de portfólio de **Victória Pedrosa** (Automação, Processos e Dados). Automação desenvolvida para um escritório de contabilidade; **esta é uma versão com dados fictícios** — nomes, CNPJs, e-mails e IDs internos foram substituídos.

## Problema de negócio
Obter guias na SEFAZ-BA envolvia captcha e acessos repetidos.

## Antes x depois
| | Antes | Depois |
|---|---|---|
| Como é feito | Acesso manual ao portal. | Robô acessa o portal, resolve o captcha e salva as guias. |

## Ganho
- Guias baixadas sem intervenção manual.

## Tecnologias
OCR (Tesseract), Python, SQLite, Selenium, pandas

## Arquivos
- `guia-tff-2026.py`
- `requirements.txt`
- `robo.py`
- `robo.spec`

## Como rodar
1. `pip install -r requirements.txt`
2. Copie `.env.exemplo` para `.env` e preencha os caminhos.
3. Execute o script principal.

## Autora
Victória Pedrosa — Product Owner do Time de IA, automação de processos contábeis e fiscais.
