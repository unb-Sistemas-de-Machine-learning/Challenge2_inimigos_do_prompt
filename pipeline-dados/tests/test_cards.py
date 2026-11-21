from pipeline.cards import main, normalizar, validar_cartao

FONTES = {"oms": {"id": "oms", "versao": "2020", "arquivo_local": "oms.txt"}}
PAGINAS = {"oms": [normalizar("Primeira página. Reduzir o tempo sedentário é recomendado."),
                   normalizar("Segunda página.\nA atividade física regular traz benefícios.")]}
TIPOS = {"anteriorizacao_cabeca"}


def cartao(**extra):
    base = {"id": "c1", "tipo_desvio": "anteriorizacao_cabeca", "texto_curto": "Ajuste a postura.",
            "fonte_id": "oms", "trecho": "Reduzir o tempo sedentário é recomendado.",
            "versao_fonte": "2020", "versao_cartao": "1", "status": "aprovado"}
    base.update(extra)
    return base


def test_cartao_valido():
    assert validar_cartao(cartao(), FONTES, PAGINAS, TIPOS) == ([], [])


def test_normalizacao_ignora_caixa_espacos_e_quebras():
    erros, avisos = validar_cartao(cartao(trecho="A ATIVIDADE   física\nregular traz benefícios."),
                                   FONTES, PAGINAS, TIPOS)
    assert erros == [] and avisos == []


def test_trecho_inexistente_aprovado_e_erro_rascunho_e_aviso():
    erros, _ = validar_cartao(cartao(trecho="frase que não existe"), FONTES, PAGINAS, TIPOS)
    assert any("não encontrado" in e for e in erros)
    erros, avisos = validar_cartao(cartao(trecho="frase que não existe", status="rascunho"), FONTES, PAGINAS, TIPOS)
    assert erros == [] and any("não encontrado" in a for a in avisos)


def test_pagina_informada_deve_conter_o_trecho():
    assert validar_cartao(cartao(pagina=1), FONTES, PAGINAS, TIPOS) == ([], [])
    erros, _ = validar_cartao(cartao(pagina=2), FONTES, PAGINAS, TIPOS)
    assert any("página 2" in e for e in erros)
    erros, _ = validar_cartao(cartao(pagina=9), FONTES, PAGINAS, TIPOS)
    assert any("fora do intervalo" in e for e in erros)


def test_versao_da_fonte_diferente():
    erros, _ = validar_cartao(cartao(versao_fonte="2019"), FONTES, PAGINAS, TIPOS)
    assert any("versao_fonte" in e for e in erros)


def test_campos_obrigatorios_tipo_fonte_e_tamanhos():
    erros, _ = validar_cartao({"id": "x"}, FONTES, PAGINAS, TIPOS)
    assert "campos obrigatórios ausentes" in erros[0]
    erros, _ = validar_cartao(cartao(tipo_desvio="outro"), FONTES, PAGINAS, TIPOS)
    assert any("tipo_desvio" in e for e in erros)
    erros, _ = validar_cartao(cartao(fonte_id="nao_existe"), FONTES, PAGINAS, TIPOS)
    assert any("não existe em sources.yaml" in e for e in erros)
    erros, _ = validar_cartao(cartao(trecho="a" * 401), FONTES, PAGINAS, TIPOS)
    assert any("trecho com mais de" in e for e in erros)


def test_arquivo_da_fonte_ausente():
    erros, _ = validar_cartao(cartao(), FONTES, {"oms": None}, TIPOS)
    assert any("ausente" in e for e in erros)


def test_cli_ponta_a_ponta(tmp_path):
    raw, cards = tmp_path / "raw", tmp_path / "cards"
    raw.mkdir(); cards.mkdir()
    (raw / "oms.txt").write_text("Reduzir o tempo sedentário é recomendado.", encoding="utf-8")
    (tmp_path / "s.yaml").write_text(
        'fontes:\n  - id: oms\n    arquivo_local: oms.txt\n    versao: "2020"\n', encoding="utf-8")
    (cards / "_tipos_desvio.yaml").write_text("tipos:\n  - anteriorizacao_cabeca\n", encoding="utf-8")
    (cards / "_template.yaml").write_text("id: ignorado\n", encoding="utf-8")
    ok = ('id: a\ntipo_desvio: anteriorizacao_cabeca\ntexto_curto: ok\nfonte_id: oms\n'
          'trecho: "Reduzir o tempo sedentário é recomendado."\nversao_fonte: "2020"\n'
          'versao_cartao: "1"\nstatus: aprovado\n')
    (cards / "a.yaml").write_text(ok, encoding="utf-8")
    args = ["--cards-dir", str(cards), "--sources", str(tmp_path / "s.yaml"), "--raw-dir", str(raw)]
    assert main(args) == 0
    (cards / "b.yaml").write_text(ok, encoding="utf-8")  # mesmo id: duplicado
    assert main(args) == 1
