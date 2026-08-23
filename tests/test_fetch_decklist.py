"""Testes do script de importação de decklists (scripts/fetch_decklist.py)."""

import yaml
from scripts.fetch_decklist import (
    _decode_html_entities,
    _normalize_color,
    _split_cards_by_section,
    convert_html_to_yaml,
    url_to_filename,
)

from fresh_and_blood.deck import load_decklist

SAMPLE_HTML = """
<html><body>
<section class="decklist-list-view block hidden">
    <h3 class="bg-gold-dark text-gold">Hero / Weapon / Equipment</h3>
    <ul class="cards-container">
        <li class="card-item group"><div class="card-name"><span>1x</span> Enigma</div></li>
        <li class="card-item group"><div class="card-name"><span>1x</span> Cosmo, Scroll of Ancestral Tapestry</div></li>
        <li class="card-item group"><div class="card-name"><span>1x</span> Silent Stilettos</div></li>
    </ul>
    <ul class="cards-container">
        <li class="card-item group"><div class="card-name"><span>2x</span> Astral Etchings (red)</div></li>
        <li class="card-item group"><div class="card-name"><span>2x</span> Look Tuff (red)</div></li>
        <li class="card-item group"><div class="card-name"><span>2x</span> Unmovable (yel)</div></li>
        <li class="card-item group"><div class="card-name"><span>2x</span> Fluid Motion (blu)</div></li>
        <li class="card-item group"><div class="card-name"><span>1x</span> Fyendal&#039;s Spring Tunic</div></li>
    </ul>
</section>
</body></html>
"""


def test_decode_html_entities():
    assert _decode_html_entities("Fyendal&#039;s Spring Tunic") == "Fyendal's Spring Tunic"
    assert _decode_html_entities("A &amp; B") == "A & B"


def test_normalize_color():
    assert _normalize_color("Unmovable (yel)") == "Unmovable (yellow)"
    assert _normalize_color("Fluid Motion (blu)") == "Fluid Motion (blue)"
    assert _normalize_color("Snatch (red)") == "Snatch (red)"


def test_split_cards_by_section():
    sections = _split_cards_by_section(SAMPLE_HTML)
    assert len(sections) == 2
    # Seção 1: hero/equip
    assert sections[0][0] == "Enigma"
    assert "Cosmo, Scroll of Ancestral Tapestry" in sections[0]
    # Seção 2: deck com quantidades e cores normalizadas
    assert "2x Astral Etchings (red)" in sections[1]
    assert "2x Unmovable (yellow)" in sections[1]
    assert "Fyendal's Spring Tunic" in sections[1]


def test_convert_html_to_yaml():
    yaml_str = convert_html_to_yaml(SAMPLE_HTML, source_url="http://exemplo.com")
    assert yaml_str is not None
    data = yaml.safe_load(yaml_str)
    assert data["hero"] == "Enigma"
    assert data["format"] == "silver-age"
    # Arena = arma + equipamentos (hero excluído)
    assert data["arena"] == ["Cosmo, Scroll of Ancestral Tapestry", "Silent Stilettos"]
    # Pool: agrupado e com cores canônicas
    pool = {e["card"]: e["qty"] for e in data["deck_pool"]}
    assert pool["Astral Etchings (red)"] == 2
    assert pool["Unmovable (yellow)"] == 2
    assert pool["Fluid Motion (blue)"] == 2
    assert "Fyendal's Spring Tunic" in pool  # equipamento no deck? -> fica no pool


def test_convert_gera_yaml_valido_pelo_deck_validator(tmp_path):
    yaml_str = convert_html_to_yaml(SAMPLE_HTML, source_url="")
    path = tmp_path / "importado.yaml"
    path.write_text(yaml_str, encoding="utf-8")
    # Não valida contra registro (cartas fictícias), apenas parse
    deck = load_decklist(path)
    assert deck.hero == "Enigma"
    assert len(deck.arena) == 2


def test_url_to_filename():
    assert (
        url_to_filename("https://fabtcg.com/decklists/richard-gillingham-enigma-ew/")
        == "richard-gillingham-enigma-ew"
    )
    assert url_to_filename("https://fabtcg.com/decklists/") == "deck"


def test_html_sem_hero_retorna_none():
    assert convert_html_to_yaml("<html><body>nada</body></html>") is None
