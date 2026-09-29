from __future__ import annotations

import json

from app.ai.contexto import serializar

PROMPT_VERSAO_ANALISE = "analise_ativo.v1"

_SYSTEM = (
    "Você descreve condições técnicas de ativos financeiros em português do Brasil.\n"
    "Regras obrigatórias:\n"
    "1. Use exclusivamente os valores do bloco DADOS. Não busque nem invente nenhum outro número.\n"
    "2. Descreva as condições técnicas detectadas de forma factual e neutra.\n"
    "3. Nunca use linguagem imperativa nem recomende ação: é proibido comprar, vender, investir, "
    "aportar, aproveitar, realizar lucro ou expressões equivalentes.\n"
    "4. Se um dado não estiver em DADOS, diga que ele não está disponível.\n"
    "5. Escreva no máximo 3 parágrafos curtos, sem listas e sem formatação Markdown."
)


def montar_prompt_analise(contexto: dict) -> tuple[str, str]:
    dados = json.dumps(serializar(contexto), ensure_ascii=False, sort_keys=True, indent=2)
    prompt = f"Descreva a situação técnica do ativo com base nos dados abaixo.\n\nDADOS:\n{dados}"
    return _SYSTEM, prompt
