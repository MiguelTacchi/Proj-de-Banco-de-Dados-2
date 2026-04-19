import re
import tkinter as tk
from tkinter import ttk, messagebox

# ==========================================================
# METADADOS
# ==========================================================

SCHEMA = {
    "categoria": ["idcategoria", "descricao"],
    "produto": ["idproduto", "nome", "descricao", "preco", "quantestoque", "categoria_idcategoria"],
    "cliente": ["idcliente", "nome", "email", "nascimento", "senha", "tipocliente_idtipocliente", "dataregistro"],
    "status": ["idstatus", "descricao"],
    "pedido": ["idpedido", "status_idstatus", "datapedido", "valortotalpedido", "cliente_idcliente"],
    "pedido_has_produto": ["idpedidoproduto", "pedido_idpedido", "produto_idproduto", "quantidade", "precounitario"]
}


# ==========================================================
# NÓ DA ÁRVORE
# ==========================================================

class No:
    def __init__(self, tipo, valor="", filhos=None):
        self.tipo = tipo
        self.valor = valor
        self.filhos = filhos if filhos else []
        self.x = 0
        self.y = 0

    def texto(self, nivel=0):
        s = "  " * nivel + self.tipo
        if self.valor:
            s += f" [{self.valor}]"
        s += "\n"
        for f in self.filhos:
            s += f.texto(nivel + 1)
        return s


# ==========================================================
# AUXILIARES
# ==========================================================

def normalizar(sql):
    return re.sub(r"\s+", " ", sql.strip())


def lista_campos(txt):
    return [c.strip() for c in txt.split(",") if c.strip()]


def extrair_aliases(base, joins):
    aliases = {}
    aliases[base["table"].lower()] = base["table"].lower()
    aliases[base["alias"].lower()] = base["table"].lower()

    for j in joins:
        aliases[j["table"].lower()] = j["table"].lower()
        aliases[j["alias"].lower()] = j["table"].lower()

    return aliases


def resolver_campo(campo, aliases):
    campo = campo.strip()
    if "." in campo:
        prefixo, atributo = campo.split(".", 1)
        return aliases.get(prefixo.lower()), atributo.lower()
    return None, campo.lower()


def validar_atributo(campo, aliases, tabelas):
    tabela, atributo = resolver_campo(campo, aliases)

    if tabela:
        if tabela not in SCHEMA:
            return False, f"Tabela '{tabela}' não existe."
        if atributo not in SCHEMA[tabela]:
            return False, f"Atributo '{atributo}' não existe em '{tabela}'."
        return True, ""

    achou = [t for t in tabelas if atributo in SCHEMA[t]]
    if not achou:
        return False, f"Atributo '{atributo}' não encontrado."
    if len(achou) > 1:
        return False, f"Atributo '{atributo}' é ambíguo. Use tabela.atributo."
    return True, ""


def atributos_da_condicao(cond):
    sem_strings = re.sub(r"'[^']*'", "", cond or "")
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_\.]*", sem_strings)
    reservadas = {"and", "or", "not"}
    return [t for t in tokens if t.lower() not in reservadas]


def separar_and(where):
    if not where:
        return []
    return [p.strip() for p in re.split(r"\s+AND\s+", where, flags=re.IGNORECASE) if p.strip()]


def prioridade(cond):
    c = cond.upper()
    if "=" in c and "<>" not in c and ">=" not in c and "<=" not in c:
        return 1
    if ">=" in c or "<=" in c or "<>" in c:
        return 2
    if ">" in c or "<" in c:
        return 3
    return 4


def tabelas_na_condicao(cond, aliases):
    tabs = set()
    for atr in atributos_da_condicao(cond):
        tabela, _ = resolver_campo(atr, aliases)
        if tabela:
            tabs.add(tabela)
    return tabs


# ==========================================================
# PARSER
# ==========================================================

def parse_sql(sql):
    sql = normalizar(sql)

    m = re.match(
        r"^SELECT\s+(?P<select>.+?)\s+FROM\s+(?P<from>.+?)(?:\s+WHERE\s+(?P<where>.+))?$",
        sql,
        re.IGNORECASE
    )
    if not m:
        raise ValueError("Consulta inválida. Use: SELECT ... FROM ... [JOIN ... ON ...] [WHERE ...]")

    select_part = m.group("select").strip()
    from_part = m.group("from").strip()
    where_part = m.group("where").strip() if m.group("where") else None

    partes = re.split(r"\s+JOIN\s+", from_part, flags=re.IGNORECASE)
    base_txt = partes[0].strip()
    joins_txt = partes[1:]

    bt = base_txt.split()
    if len(bt) == 1:
        base = {"table": bt[0], "alias": bt[0]}
    elif len(bt) == 2:
        base = {"table": bt[0], "alias": bt[1]}
    else:
        raise ValueError("Cláusula FROM inválida.")

    joins = []
    for p in joins_txt:
        j = re.match(
            r"^([A-Za-z_][A-Za-z0-9_]*)(?:\s+([A-Za-z_][A-Za-z0-9_]*))?\s+ON\s+(.+)$",
            p,
            re.IGNORECASE
        )
        if not j:
            raise ValueError(f"JOIN inválido: {p}")

        joins.append({
            "table": j.group(1),
            "alias": j.group(2) if j.group(2) else j.group(1),
            "condition": j.group(3).strip()
        })

    return {
        "select": lista_campos(select_part),
        "from": base,
        "joins": joins,
        "where": where_part
    }


# ==========================================================
# VALIDAÇÃO
# ==========================================================

def validar(parsed):
    base = parsed["from"]["table"].lower()
    if base not in SCHEMA:
        raise ValueError(f"Tabela '{base}' não existe.")

    for j in parsed["joins"]:
        if j["table"].lower() not in SCHEMA:
            raise ValueError(f"Tabela '{j['table']}' não existe.")

    aliases = extrair_aliases(parsed["from"], parsed["joins"])
    tabelas = [parsed["from"]["table"].lower()] + [j["table"].lower() for j in parsed["joins"]]

    for campo in parsed["select"]:
        ok, msg = validar_atributo(campo, aliases, tabelas)
        if not ok:
            raise ValueError("Erro no SELECT: " + msg)

    if parsed["where"]:
        for atr in atributos_da_condicao(parsed["where"]):
            if atr.lower() in aliases:
                continue
            ok, msg = validar_atributo(atr, aliases, tabelas)
            if not ok:
                raise ValueError("Erro no WHERE: " + msg)

    for j in parsed["joins"]:
        for atr in atributos_da_condicao(j["condition"]):
            if atr.lower() in aliases:
                continue
            ok, msg = validar_atributo(atr, aliases, tabelas)
            if not ok:
                raise ValueError("Erro no JOIN: " + msg)

    return aliases


# ==========================================================
# ÁLGEBRA
# ==========================================================

def algebra_relacional(parsed):
    expr = parsed["from"]["table"]
    for j in parsed["joins"]:
        expr = f"({expr} ⋈[{j['condition']}] {j['table']})"

    if parsed["where"]:
        expr = f"σ[{parsed['where']}]({expr})"

    expr = f"π[{', '.join(parsed['select'])}]({expr})"
    return expr


def algebra_otimizada(parsed):
    aliases = extrair_aliases(parsed["from"], parsed["joins"])
    conds = separar_and(parsed["where"])
    conds.sort(key=prioridade)

    por_tabela = {}
    gerais = []

    for cond in conds:
        tabs = tabelas_na_condicao(cond, aliases)
        if len(tabs) == 1:
            t = list(tabs)[0]
            por_tabela.setdefault(t, []).append(cond)
        else:
            gerais.append(cond)

    base_nome = parsed["from"]["table"].lower()
    expr = base_nome

    for cond in por_tabela.get(base_nome, []):
        expr = f"σ[{cond}]({expr})"

    for j in parsed["joins"]:
        tabela_join = j["table"].lower()
        lado = tabela_join
        for cond in por_tabela.get(tabela_join, []):
            lado = f"σ[{cond}]({lado})"
        expr = f"({expr} ⋈[{j['condition']}] {lado})"

    for cond in gerais:
        expr = f"σ[{cond}]({expr})"

    expr = f"π[{', '.join(parsed['select'])}]({expr})"

    explicacao = [
        "Heurísticas aplicadas:",
        "1. Seleções mais restritivas primeiro.",
        "2. Seleções empurradas para perto das tabelas quando possível.",
        "3. JOINs mantidos com condição ON para evitar produto cartesiano.",
        "4. Projeção aplicada ao final."
    ]

    return expr, "\n".join(explicacao)


def passos_algebra(parsed):
    passos = []
    expr = parsed["from"]["table"]
    passos.append(f"1. Relação base: {expr}")

    n = 2
    for j in parsed["joins"]:
        expr = f"({expr} ⋈[{j['condition']}] {j['table']})"
        passos.append(f"{n}. Após JOIN: {expr}")
        n += 1

    if parsed["where"]:
        expr = f"σ[{parsed['where']}]({expr})"
        passos.append(f"{n}. Após seleção: {expr}")
        n += 1

    expr = f"π[{', '.join(parsed['select'])}]({expr})"
    passos.append(f"{n}. Após projeção: {expr}")

    return "\n".join(passos)


# ==========================================================
# PLANO E ÁRVORE
# ==========================================================

def plano_execucao(parsed):
    aliases = extrair_aliases(parsed["from"], parsed["joins"])
    conds = separar_and(parsed["where"])
    conds.sort(key=prioridade)

    por_tabela = {}
    gerais = []

    for cond in conds:
        tabs = tabelas_na_condicao(cond, aliases)
        if len(tabs) == 1:
            por_tabela.setdefault(list(tabs)[0], []).append(cond)
        else:
            gerais.append(cond)

    passos = []
    i = 1

    base = parsed["from"]["table"]
    passos.append(f"{i}. Ler tabela base: {base}")
    i += 1

    for cond in por_tabela.get(base.lower(), []):
        passos.append(f"{i}. Aplicar seleção em {base}: {cond}")
        i += 1

    for j in parsed["joins"]:
        t = j["table"]
        passos.append(f"{i}. Ler tabela para JOIN: {t}")
        i += 1

        for cond in por_tabela.get(t.lower(), []):
            passos.append(f"{i}. Aplicar seleção em {t}: {cond}")
            i += 1

        passos.append(f"{i}. Realizar JOIN com {t} usando: {j['condition']}")
        i += 1

    for cond in gerais:
        passos.append(f"{i}. Aplicar seleção geral: {cond}")
        i += 1

    passos.append(f"{i}. Aplicar projeção final: {', '.join(parsed['select'])}")
    return "\n".join(passos)


def arvore(parsed, otimizada=False):
    if not otimizada:
        raiz = No("TABELA", parsed["from"]["table"])

        if parsed["where"]:
            raiz = No("SELEÇÃO", parsed["where"], [raiz])

        for j in parsed["joins"]:
            raiz = No("JOIN", j["condition"], [raiz, No("TABELA", j["table"])])

        return No("PROJEÇÃO", ", ".join(parsed["select"]), [raiz])

    aliases = extrair_aliases(parsed["from"], parsed["joins"])
    conds = separar_and(parsed["where"])
    conds.sort(key=prioridade)

    por_tabela = {}
    gerais = []

    for cond in conds:
        tabs = tabelas_na_condicao(cond, aliases)
        if len(tabs) == 1:
            por_tabela.setdefault(list(tabs)[0], []).append(cond)
        else:
            gerais.append(cond)

    base = parsed["from"]["table"]
    raiz = No("TABELA", base)
    for cond in por_tabela.get(base.lower(), []):
        raiz = No("SELEÇÃO", cond, [raiz])

    for j in parsed["joins"]:
        lado = No("TABELA", j["table"])
        for cond in por_tabela.get(j["table"].lower(), []):
            lado = No("SELEÇÃO", cond, [lado])
        raiz = No("JOIN", j["condition"], [raiz, lado])

    for cond in gerais:
        raiz = No("SELEÇÃO", cond, [raiz])

    return No("PROJEÇÃO", ", ".join(parsed["select"]), [raiz])


# ==========================================================
# DESENHO DO GRAFO
# ==========================================================

def folhas(no):
    if not no.filhos:
        return 1
    return sum(folhas(f) for f in no.filhos)


def posicionar(no, xi, xf, y=60, dy=110):
    no.y = y
    if not no.filhos:
        no.x = (xi + xf) // 2
        return

    total = sum(folhas(f) for f in no.filhos)
    atual = xi
    xs = []

    for f in no.filhos:
        largura = (xf - xi) * folhas(f) / total
        fi, ff = atual, atual + largura
        posicionar(f, fi, ff, y + dy, dy)
        xs.append(f.x)
        atual += largura

    no.x = sum(xs) // len(xs)


def cor(tipo):
    return {
        "PROJEÇÃO": "#2563eb",
        "SELEÇÃO": "#16a34a",
        "JOIN": "#ca8a04",
        "TABELA": "#6b7280"
    }.get(tipo, "#6b7280")


def desenhar(canvas, no):
    w, h = 170, 46
    x1, y1 = no.x - w // 2, no.y - h // 2
    x2, y2 = no.x + w // 2, no.y + h // 2

    canvas.create_rectangle(x1, y1, x2, y2, fill=cor(no.tipo), outline="white", width=2)
    canvas.create_text(
        no.x, no.y,
        text=f"{no.tipo}\n{no.valor}",
        fill="white",
        font=("Arial", 9, "bold"),
        width=150
    )

    for f in no.filhos:
        canvas.create_line(no.x, y2, f.x, f.y - 23, fill="white", width=2)
        desenhar(canvas, f)


# ==========================================================
# INTERFACE
# ==========================================================

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Processador de Consultas SQL")
        self.root.geometry("1280x820")

        self.criar_interface()

    def criar_interface(self):
        topo = ttk.Frame(self.root, padding=10)
        topo.pack(fill="x")

        ttk.Label(topo, text="Digite a consulta SQL:", font=("Arial", 12, "bold")).pack(anchor="w")

        self.txt_sql = tk.Text(self.root, height=7, font=("Consolas", 11))
        self.txt_sql.pack(fill="x", padx=10)

        self.txt_sql.insert(
            "1.0",
            "SELECT c.nome, p.valortotalpedido, s.descricao\n"
            "FROM cliente c\n"
            "JOIN pedido p ON c.idcliente = p.cliente_idcliente\n"
            "JOIN status s ON p.status_idstatus = s.idstatus\n"
            "WHERE c.nome = 'Miguel' AND p.valortotalpedido > 100"
        )

        botoes = ttk.Frame(self.root, padding=10)
        botoes.pack(fill="x")

        ttk.Button(botoes, text="Processar Consulta", command=self.processar).pack(side="left", padx=5)
        ttk.Button(botoes, text="Inserir Exemplo", command=self.exemplo).pack(side="left", padx=5)
        ttk.Button(botoes, text="Limpar", command=self.limpar).pack(side="left", padx=5)

        self.abas = ttk.Notebook(self.root)
        self.abas.pack(fill="both", expand=True, padx=10, pady=10)

        self.aba_validacao = self.criar_aba_texto("Validação")
        self.aba_algebra = self.criar_aba_texto("Álg. Relacional")
        self.aba_calculo = self.criar_aba_texto("Cálculo da Álgebra")
        self.aba_otimizada = self.criar_aba_texto("Álg. Otimizada")
        self.aba_plano = self.criar_aba_texto("Plano de Execução")
        self.aba_grafo = self.criar_aba_canvas("Grafo Visual")
        self.aba_grafo_ot = self.criar_aba_canvas("Grafo Otimizado")

    def criar_aba_texto(self, titulo):
        frame = ttk.Frame(self.abas)
        self.abas.add(frame, text=titulo)

        txt = tk.Text(frame, wrap="word", font=("Consolas", 11))
        txt.pack(fill="both", expand=True, side="left")

        scroll = ttk.Scrollbar(frame, orient="vertical", command=txt.yview)
        scroll.pack(side="right", fill="y")
        txt.configure(yscrollcommand=scroll.set)
        return txt

    def criar_aba_canvas(self, titulo):
        frame = ttk.Frame(self.abas)
        self.abas.add(frame, text=titulo)

        canvas = tk.Canvas(frame, bg="#111827", highlightthickness=0, scrollregion=(0, 0, 1800, 1200))
        canvas.pack(fill="both", expand=True, side="left")

        sy = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        sy.pack(side="right", fill="y")
        sx = ttk.Scrollbar(frame, orient="horizontal", command=canvas.xview)
        sx.pack(side="bottom", fill="x")

        canvas.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        return canvas

    def exemplo(self):
        self.txt_sql.delete("1.0", tk.END)
        self.txt_sql.insert(
            "1.0",
            "SELECT c.nome, p.valortotalpedido, s.descricao\n"
            "FROM cliente c\n"
            "JOIN pedido p ON c.idcliente = p.cliente_idcliente\n"
            "JOIN status s ON p.status_idstatus = s.idstatus\n"
            "WHERE c.nome = 'Miguel' AND p.valortotalpedido > 100"
        )

    def limpar(self):
        for t in [self.aba_validacao, self.aba_algebra, self.aba_calculo, self.aba_otimizada, self.aba_plano]:
            t.delete("1.0", tk.END)

        self.aba_grafo.delete("all")
        self.aba_grafo_ot.delete("all")

    def escrever(self, widget, texto):
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, texto)

    def desenhar_grafo(self, canvas, raiz):
        canvas.delete("all")
        posicionar(raiz, 80, 1700)
        desenhar(canvas, raiz)

    def processar(self):
        try:
            self.limpar()
            sql = self.txt_sql.get("1.0", tk.END).strip()

            parsed = parse_sql(sql)
            aliases = validar(parsed)

            self.escrever(
                self.aba_validacao,
                "Consulta válida.\n\n"
                f"SELECT: {parsed['select']}\n"
                f"FROM: {parsed['from']}\n"
                f"JOINS: {parsed['joins']}\n"
                f"WHERE: {parsed['where']}\n"
                f"ALIASES: {aliases}"
            )

            self.escrever(self.aba_algebra, algebra_relacional(parsed))
            self.escrever(self.aba_calculo, passos_algebra(parsed))

            expr_ot, exp = algebra_otimizada(parsed)
            self.escrever(self.aba_otimizada, expr_ot + "\n\n" + exp)

            self.escrever(self.aba_plano, plano_execucao(parsed))

            raiz_normal = arvore(parsed, otimizada=False)
            raiz_ot = arvore(parsed, otimizada=True)

            self.desenhar_grafo(self.aba_grafo, raiz_normal)
            self.desenhar_grafo(self.aba_grafo_ot, raiz_ot)

        except Exception as e:
            messagebox.showerror("Erro", str(e))


# ==========================================================
# EXECUÇÃO
# ==========================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()