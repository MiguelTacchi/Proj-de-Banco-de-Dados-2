# Processador de Consultas SQL

Projeto acadêmico desenvolvido para a disciplina de Banco de Dados, com o objetivo de simular o processamento de consultas SQL em um banco de dados, desde a entrada da consulta até a geração do plano de execução.

## O que o sistema faz

O usuário digita uma consulta SQL e o sistema:

- Valida a consulta (tabelas e atributos)
- Converte para Álgebra Relacional
- Mostra o passo a passo da álgebra
- Aplica uma otimização simples
- Exibe o grafo de operadores
- Mostra o plano de execução

## Funcionalidades

- Suporte a consultas com `SELECT`, `FROM`, `JOIN` e `WHERE`
- Conversão para álgebra relacional utilizando:
  - σ (seleção)
  - π (projeção)
  - ⋈ (junção)
- Validação de tabelas e atributos com base no modelo definido
- Visualização do fluxo de execução da consulta

## Como executar

```bash
python processador_consultas.py
