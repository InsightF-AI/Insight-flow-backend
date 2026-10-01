from __future__ import annotations

import json

from app.ai.contexto import serializar

PROMPT_VERSAO_RESUMO = "resumo_diario.v1"

_SYSTEM = (
    "Você resume a situação da carteira de um investidor em português do Brasil.\n"
    "Regras obrigatórias:\n"
    "1. Use exclusivamente os valores do bloco DADOS. Não busque nem invente nenhum outro número.\n"
    "2. Campos de percentual e de distribuição estão em fração decimal "
    "(0.05 equivale a 5%). Converta para porcentagem ao escrever.\n"
    "3. Valores monetários estão em BRL quando o campo termina em _brl.\n"
    "4. Descreva de forma factual e neutra: desempenho, concentração e comparação com o CDI "
    "quando houver.\n"
    "5. Nunca use linguagem imperativa nem recomende ação: é proibido comprar, vender, investir, "
    "aportar, aproveitar, realizar lucro ou expressões equivalentes.\n"
    "6. Se um dado não estiver em DADOS, diga que ele não está disponível.\n"
    "7. Escreva no máximo 3 parágrafos curtos, sem listas e sem formatação Markdown."
)


def montar_prompt_resumo(contexto: dict) -> tuple[str, str]:
    dados = json.dumps(serializar(contexto), ensure_ascii=False, sort_keys=True, indent=2)
    prompt = f"Resuma a situação da carteira com base nos dados abaixo.\n\nDADOS:\n{dados}"
    return _SYSTEM, prompt
