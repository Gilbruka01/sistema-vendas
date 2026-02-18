from flask import Flask, render_template, request, redirect, session, flash, url_for
import sqlite3
from datetime import date, timedelta
from urllib.parse import quote
import bcrypt
from functools import wraps
import os

app = Flask(__name__)

# ✅ Padrão profissional: SECRET_KEY via variável de ambiente
# No Windows PowerShell (exemplo):  $env:SECRET_KEY="minha-chave-super-forte"
# (Fallback "dev-key" serve só para desenvolvimento local)
app.secret_key = os.getenv("SECRET_KEY", "dev-key")


# -----------------------------
# HELPERS
# -----------------------------
def db():
    # check_same_thread=False evita alguns problemas quando o Flask reinicia em debug
    con = sqlite3.connect("database.db", check_same_thread=False)
    return con


def coluna_existe(cursor, tabela, coluna) -> bool:
    cursor.execute(f"PRAGMA table_info({tabela})")
    cols = [row[1] for row in cursor.fetchall()]
    return coluna in cols


def apenas_numeros(texto: str) -> str:
    return "".join(ch for ch in (texto or "") if ch.isdigit())


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Faça login para acessar o sistema.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def current_user_id() -> int:
    return int(session["user_id"])


# -----------------------------
# DATA / VENCIMENTO
# -----------------------------
def primeiro_dia_util(ano: int, mes: int) -> date:
    d = date(ano, mes, 1)
    while d.weekday() >= 5:  # 5=sábado, 6=domingo
        d += timedelta(days=1)
    return d


def vencimento_do_pedido(data_pedido: date) -> date:
    ano = data_pedido.year
    mes = data_pedido.month
    if mes == 12:
        return primeiro_dia_util(ano + 1, 1)
    return primeiro_dia_util(ano, mes + 1)


# -----------------------------
# BANCO / MIGRAÇÃO
# -----------------------------
def criar_banco():
    conexao = db()
    cursor = conexao.cursor()

    # usuários
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        senha_hash BLOB NOT NULL
    )
    """)

    # clientes
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        nome TEXT NOT NULL,
        telefone TEXT
    )
    """)

    # produtos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS produtos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        nome TEXT NOT NULL,
        preco REAL NOT NULL
    )
    """)

    # pedidos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pedidos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        cliente_id INTEGER,
        produto_id INTEGER,
        quantidade INTEGER,
        data TEXT,
        vencimento TEXT,
        pago INTEGER DEFAULT 0
    )
    """)

    # estoque (por produto, por usuário)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS estoque (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        produto_id INTEGER NOT NULL,
        quantidade INTEGER NOT NULL DEFAULT 0,
        minimo INTEGER NOT NULL DEFAULT 0,
        UNIQUE(usuario_id, produto_id)
    )
    """)

    # Migração para bancos antigos
    for tabela, colunas in [
        ("clientes", ["usuario_id"]),
        ("produtos", ["usuario_id"]),
        ("pedidos", ["usuario_id", "vencimento"]),
        ("estoque", ["usuario_id", "produto_id", "quantidade", "minimo"]),
    ]:
        try:
            for col in colunas:
                if not coluna_existe(cursor, tabela, col):
                    if col in ("vencimento",):
                        cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {col} TEXT")
                    elif col in ("quantidade", "minimo", "usuario_id", "produto_id"):
                        cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {col} INTEGER")
                    else:
                        cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            # tabela não existe (caso bem antigo) — ignore
            pass

    conexao.commit()
    conexao.close()


def criar_usuario(username: str, senha: str):
    senha_hash = bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt())
    conexao = db()
    cursor = conexao.cursor()
    cursor.execute(
        "INSERT INTO usuarios (username, senha_hash) VALUES (?, ?)",
        (username, senha_hash)
    )
    conexao.commit()
    conexao.close()


def autenticar_usuario(username: str, senha: str):
    conexao = db()
    cursor = conexao.cursor()
    cursor.execute("SELECT id, senha_hash FROM usuarios WHERE username = ?", (username,))
    row = cursor.fetchone()
    conexao.close()

    if not row:
        return None

    user_id, senha_hash = row

    if isinstance(senha_hash, str):
        senha_hash = senha_hash.encode("utf-8")

    if bcrypt.checkpw(senha.encode("utf-8"), senha_hash):
        return user_id

    return None


# -----------------------------
# AUTH
# -----------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        senha = request.form.get("senha", "")
        senha2 = request.form.get("senha2", "")

        if not username or len(username) < 3:
            flash("Usuário inválido (mínimo 3 caracteres).", "warning")
            return redirect("/register")

        if not senha or not senha2:
            flash("Preencha senha e confirmação de senha.", "warning")
            return redirect("/register")

        if senha != senha2:
            flash("As senhas não conferem.", "error")
            return redirect("/register")

        if len(senha) < 6:
            flash("Senha fraca (mínimo 6 caracteres).", "warning")
            return redirect("/register")

        try:
            criar_usuario(username, senha)
        except sqlite3.IntegrityError:
            flash("Esse usuário já existe. Tente outro.", "warning")
            return redirect("/register")

        flash("Conta criada! Faça login para continuar ✅", "success")
        return redirect("/login")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        senha = request.form.get("senha", "")

        if not username or not senha:
            flash("Preencha usuário e senha.", "warning")
            return redirect("/login")

        user_id = autenticar_usuario(username, senha)
        if not user_id:
            flash("Usuário ou senha inválidos.", "error")
            return redirect("/login")

        session["user_id"] = user_id
        session["username"] = username
        flash("Login realizado com sucesso ✅", "success")
        return redirect("/")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("Você saiu da conta.", "info")
    return redirect("/login")


# -----------------------------
# DASHBOARD (PROTEGIDO)
# -----------------------------
@app.route("/")
@login_required
def home():
    uid = current_user_id()
    conexao = db()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT SUM(produtos.preco * pedidos.quantidade)
        FROM pedidos
        JOIN produtos ON produtos.id = pedidos.produto_id
        WHERE pedidos.pago = 0 AND pedidos.usuario_id = ?
    """, (uid,))
    total_aberto = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT SUM(produtos.preco * pedidos.quantidade)
        FROM pedidos
        JOIN produtos ON produtos.id = pedidos.produto_id
        WHERE pedidos.pago = 1 AND pedidos.usuario_id = ?
    """, (uid,))
    total_pago = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM clientes WHERE usuario_id = ?", (uid,))
    total_clientes = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM pedidos WHERE usuario_id = ?", (uid,))
    total_pedidos = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT clientes.nome, SUM(produtos.preco * pedidos.quantidade) AS total
        FROM pedidos
        JOIN clientes ON clientes.id = pedidos.cliente_id
        JOIN produtos ON produtos.id = pedidos.produto_id
        WHERE pedidos.pago = 0 AND pedidos.usuario_id = ?
        GROUP BY clientes.id
        ORDER BY total DESC
        LIMIT 5
    """, (uid,))
    top_devedores = cursor.fetchall()

    cursor.execute("""
        SELECT produtos.nome, SUM(pedidos.quantidade) AS qtd
        FROM pedidos
        JOIN produtos ON produtos.id = pedidos.produto_id
        WHERE pedidos.usuario_id = ?
        GROUP BY produtos.id
        ORDER BY qtd DESC
        LIMIT 5
    """, (uid,))
    top_produtos = cursor.fetchall()

    cursor.execute("""
        SELECT substr(pedidos.data, 1, 7) AS mes, SUM(produtos.preco * pedidos.quantidade) AS total
        FROM pedidos
        JOIN produtos ON produtos.id = pedidos.produto_id
        WHERE pedidos.usuario_id = ?
        GROUP BY mes
        ORDER BY mes DESC
        LIMIT 6
    """, (uid,))
    meses = cursor.fetchall()

    conexao.close()

    meses = list(reversed(meses))
    chart_labels = [m[0] for m in meses]
    chart_values = [float(m[1] or 0) for m in meses]

    return render_template(
        "dashboard.html",
        total_aberto=total_aberto,
        total_pago=total_pago,
        total_clientes=total_clientes,
        total_pedidos=total_pedidos,
        top_devedores=top_devedores,
        top_produtos=top_produtos,
        chart_labels=chart_labels,
        chart_values=chart_values
    )


# -----------------------------
# PRODUTOS (PROTEGIDO)
# -----------------------------
@app.route("/produtos", methods=["GET", "POST"])
@login_required
def produtos():
    uid = current_user_id()

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        preco = request.form.get("preco", "").strip()

        if not nome:
            flash("Nome do produto inválido!", "warning")
            return redirect("/produtos")

        try:
            preco = float(preco)
            if preco <= 0:
                flash("Preço inválido!", "warning")
                return redirect("/produtos")
        except ValueError:
            flash("Preço inválido!", "warning")
            return redirect("/produtos")

        conexao = db()
        cursor = conexao.cursor()
        cursor.execute(
            "INSERT INTO produtos (usuario_id, nome, preco) VALUES (?, ?, ?)",
            (uid, nome, preco)
        )
        conexao.commit()

        # garante linha de estoque para o novo produto
        produto_id = cursor.lastrowid
        cursor.execute("""
            INSERT OR IGNORE INTO estoque (usuario_id, produto_id, quantidade, minimo)
            VALUES (?, ?, 0, 0)
        """, (uid, produto_id))
        conexao.commit()
        conexao.close()

        flash("Produto cadastrado com sucesso ✅", "success")
        return redirect("/produtos")

    conexao = db()
    cursor = conexao.cursor()
    cursor.execute("SELECT id, nome, preco FROM produtos WHERE usuario_id = ? ORDER BY nome", (uid,))
    lista_produtos = cursor.fetchall()
    conexao.close()

    return render_template("produtos.html", produtos=lista_produtos)


@app.route("/produtos/editar/<int:produto_id>", methods=["GET", "POST"])
@login_required
def editar_produto(produto_id):
    uid = current_user_id()
    conexao = db()
    cursor = conexao.cursor()

    cursor.execute("SELECT id, nome, preco FROM produtos WHERE id = ? AND usuario_id = ?", (produto_id, uid))
    produto = cursor.fetchone()
    if not produto:
        conexao.close()
        flash("Produto não encontrado.", "error")
        return redirect("/produtos")

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        preco_raw = request.form.get("preco", "").strip()

        if not nome:
            conexao.close()
            flash("Nome inválido.", "warning")
            return redirect(f"/produtos/editar/{produto_id}")

        try:
            preco = float(preco_raw)
            if preco <= 0:
                raise ValueError
        except ValueError:
            conexao.close()
            flash("Preço inválido.", "warning")
            return redirect(f"/produtos/editar/{produto_id}")

        cursor.execute(
            "UPDATE produtos SET nome = ?, preco = ? WHERE id = ? AND usuario_id = ?",
            (nome, preco, produto_id, uid)
        )
        conexao.commit()
        conexao.close()

        flash("Produto atualizado ✅", "success")
        return redirect("/produtos")

    conexao.close()
    return render_template("produto_editar.html", produto=produto)


@app.route("/produtos/excluir/<int:produto_id>", methods=["POST"])
@login_required
def excluir_produto(produto_id):
    uid = current_user_id()
    conexao = db()
    cursor = conexao.cursor()

    cursor.execute("SELECT id FROM produtos WHERE id = ? AND usuario_id = ?", (produto_id, uid))
    if not cursor.fetchone():
        conexao.close()
        flash("Produto não encontrado.", "error")
        return redirect("/produtos")

    cursor.execute("SELECT 1 FROM pedidos WHERE produto_id = ? AND usuario_id = ? LIMIT 1", (produto_id, uid))
    if cursor.fetchone():
        conexao.close()
        flash("Não dá para excluir: esse produto já tem pedidos vinculados. (Edite o nome/preço ou crie outro).", "warning")
        return redirect("/produtos")

    cursor.execute("DELETE FROM estoque WHERE produto_id = ? AND usuario_id = ?", (produto_id, uid))
    cursor.execute("DELETE FROM produtos WHERE id = ? AND usuario_id = ?", (produto_id, uid))

    conexao.commit()
    conexao.close()

    flash("Produto excluído ✅", "success")
    return redirect("/produtos")


# -----------------------------
# CLIENTES (PROTEGIDO)
# -----------------------------
@app.route("/clientes", methods=["GET", "POST"])
@login_required
def clientes():
    uid = current_user_id()

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        telefone = apenas_numeros(request.form.get("telefone", ""))

        if not nome:
            flash("Nome inválido!", "warning")
            return redirect("/clientes")

        conexao = db()
        cursor = conexao.cursor()
        cursor.execute(
            "INSERT INTO clientes (usuario_id, nome, telefone) VALUES (?, ?, ?)",
            (uid, nome, telefone)
        )
        conexao.commit()
        conexao.close()

        flash("Cliente cadastrado com sucesso ✅", "success")
        return redirect("/clientes")

    conexao = db()
    cursor = conexao.cursor()
    cursor.execute("SELECT id, nome, telefone FROM clientes WHERE usuario_id = ? ORDER BY nome", (uid,))
    lista_clientes = cursor.fetchall()
    conexao.close()

    return render_template("clientes.html", clientes=lista_clientes)


# -----------------------------
# PEDIDOS (PROTEGIDO)
# -----------------------------
@app.route("/pedidos", methods=["GET", "POST"])
@login_required
def pedidos():
    uid = current_user_id()
    conexao = db()
    cursor = conexao.cursor()

    cursor.execute("SELECT id, nome, telefone FROM clientes WHERE usuario_id = ? ORDER BY nome", (uid,))
    lista_clientes = cursor.fetchall()

    cursor.execute("SELECT id, nome, preco FROM produtos WHERE usuario_id = ? ORDER BY nome", (uid,))
    lista_produtos = cursor.fetchall()

    if request.method == "POST":
        try:
            cliente_id = int(request.form["cliente_id"])
            produto_id = int(request.form["produto_id"])
            quantidade = int(request.form["quantidade"])
            if quantidade < 1:
                flash("Quantidade inválida!", "warning")
                return redirect("/pedidos")
        except ValueError:
            flash("Dados inválidos!", "error")
            return redirect("/pedidos")

        cursor.execute("SELECT 1 FROM clientes WHERE id = ? AND usuario_id = ?", (cliente_id, uid))
        if not cursor.fetchone():
            flash("Cliente inválido!", "error")
            return redirect("/pedidos")

        cursor.execute("SELECT 1 FROM produtos WHERE id = ? AND usuario_id = ?", (produto_id, uid))
        if not cursor.fetchone():
            flash("Produto inválido!", "error")
            return redirect("/pedidos")

        hoje = date.today()
        venc = vencimento_do_pedido(hoje)

        cursor.execute("""
            INSERT INTO pedidos (usuario_id, cliente_id, produto_id, quantidade, data, vencimento, pago)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """, (uid, cliente_id, produto_id, quantidade, hoje.isoformat(), venc.isoformat()))

        conexao.commit()
        conexao.close()

        flash("Pedido criado com sucesso ✅", "success")
        return redirect("/listar_pedidos")

    conexao.close()
    return render_template("pedidos.html", clientes=lista_clientes, produtos=lista_produtos)


@app.route("/listar_pedidos")
@login_required
def listar_pedidos():
    uid = current_user_id()
    status = request.args.get("status", "todos")  # todos | aberto | pago

    where_extra = ""
    params = [uid]

    if status == "aberto":
        where_extra = " AND pedidos.pago = 0"
    elif status == "pago":
        where_extra = " AND pedidos.pago = 1"

    conexao = db()
    cursor = conexao.cursor()

    cursor.execute(f"""
        SELECT
            pedidos.id,
            pedidos.data,
            clientes.nome,
            produtos.nome,
            produtos.preco,
            pedidos.quantidade,
            (produtos.preco * pedidos.quantidade) AS total,
            pedidos.pago
        FROM pedidos
        JOIN clientes ON clientes.id = pedidos.cliente_id
        JOIN produtos ON produtos.id = pedidos.produto_id
        WHERE pedidos.usuario_id = ? {where_extra}
        ORDER BY pedidos.id DESC
    """, params)

    lista_pedidos = cursor.fetchall()
    conexao.close()

    return render_template("listar_pedidos.html", pedidos=lista_pedidos, status=status)


@app.route("/marcar_pago/<int:pedido_id>")
@login_required
def marcar_pago(pedido_id):
    uid = current_user_id()
    conexao = db()
    cursor = conexao.cursor()

    cursor.execute(
        "UPDATE pedidos SET pago = 1 WHERE id = ? AND usuario_id = ?",
        (pedido_id, uid)
    )
    conexao.commit()
    conexao.close()

    flash("Pedido marcado como pago ✅", "success")
    return redirect("/listar_pedidos")


# -----------------------------
# COBRANÇAS COM JUROS (PROTEGIDO)
# -----------------------------
@app.route("/cobrancas")
@login_required
def cobrancas():
    uid = current_user_id()
    conexao = db()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT
            clientes.id,
            clientes.nome,
            clientes.telefone,
            pedidos.data,
            pedidos.vencimento,
            produtos.nome,
            produtos.preco,
            pedidos.quantidade
        FROM pedidos
        JOIN clientes ON clientes.id = pedidos.cliente_id
        JOIN produtos ON produtos.id = pedidos.produto_id
        WHERE pedidos.pago = 0 AND pedidos.usuario_id = ?
        ORDER BY clientes.nome, pedidos.data
    """, (uid,))

    linhas = cursor.fetchall()
    conexao.close()

    hoje = date.today()
    taxa_juros_dia = 0.03  # 3% ao dia (juros simples)

    por_cliente = {}

    for (cliente_id, nome, telefone, data_pedido, vencimento, prod_nome, preco, qtd) in linhas:
        if cliente_id not in por_cliente:
            por_cliente[cliente_id] = {
                "nome": nome,
                "telefone": telefone,
                "itens": [],
                "principal": 0.0,
                "juros": 0.0
            }

        total_item = float(preco) * int(qtd)
        por_cliente[cliente_id]["principal"] += total_item

        if vencimento:
            venc = date.fromisoformat(vencimento)
        else:
            venc = vencimento_do_pedido(date.fromisoformat(data_pedido))

        dias_atraso = (hoje - venc).days
        if dias_atraso < 0:
            dias_atraso = 0

        juros_item = total_item * taxa_juros_dia * dias_atraso
        por_cliente[cliente_id]["juros"] += juros_item

        por_cliente[cliente_id]["itens"].append({
            "produto": prod_nome,
            "qtd": int(qtd),
            "total": total_item,
            "venc": venc.isoformat(),
            "dias": dias_atraso,
            "juros": juros_item
        })

    lista_cobrancas = []

    for _, info in por_cliente.items():
        nome = info["nome"]
        telefone = apenas_numeros(info["telefone"])
        principal = info["principal"]
        juros = info["juros"]
        total_final = principal + juros

        if not telefone:
            continue

        linhas_msg = [f"Olá {nome}! 👋", "", "Resumo do seu consumo de Refrigerantes/Energéticos do mês anterior (em aberto):"]
        for it in info["itens"]:
            linhas_msg.append(
                f"- {it['produto']} x{it['qtd']} = R$ {it['total']:.2f} | atraso: {it['dias']}d | juros: R$ {it['juros']:.2f}"
            )

        linhas_msg += [
            "",
            f"Subtotal: R$ {principal:.2f}",
            f"Juros (3% ao dia): R$ {juros:.2f}",
            f"Total atualizado: R$ {total_final:.2f}",
            "",
            "Quando puder, me confirma o pagamento 🙂"
        ]

        mensagem = "\n".join(linhas_msg)
        link = f"https://wa.me/55{telefone}?text={quote(mensagem)}"

        lista_cobrancas.append({
            "nome": nome,
            "total": total_final,
            "link_whatsapp": link
        })

    return render_template("cobrancas.html", clientes=lista_cobrancas)


# -----------------------------
# ESTOQUE (PROTEGIDO)
# -----------------------------
@app.route("/estoque", methods=["GET", "POST"])
@login_required
def estoque():
    uid = current_user_id()
    conexao = db()
    cursor = conexao.cursor()

    cursor.execute("SELECT id FROM produtos WHERE usuario_id = ?", (uid,))
    produtos_ids = [r[0] for r in cursor.fetchall()]

    for pid in produtos_ids:
        cursor.execute("""
            INSERT OR IGNORE INTO estoque (usuario_id, produto_id, quantidade, minimo)
            VALUES (?, ?, 0, 0)
        """, (uid, pid))
    conexao.commit()

    if request.method == "POST":
        try:
            produto_id = int(request.form["produto_id"])
            acao = request.form["acao"]  # "add" ou "sub"
            qtd = int(request.form["qtd"])
            minimo = request.form.get("minimo", "").strip()
            minimo_val = int(minimo) if minimo != "" else None

            if acao not in ("add", "sub"):
                raise ValueError("Ação inválida")

            if qtd < 1:
                flash("Quantidade inválida (mínimo 1).", "warning")
                return redirect("/estoque")

        except Exception:
            conexao.close()
            flash("Dados inválidos.", "error")
            return redirect("/estoque")

        cursor.execute("SELECT 1 FROM produtos WHERE id = ? AND usuario_id = ?", (produto_id, uid))
        if not cursor.fetchone():
            conexao.close()
            flash("Produto inválido.", "error")
            return redirect("/estoque")

        cursor.execute("""
            SELECT quantidade, minimo FROM estoque
            WHERE usuario_id = ? AND produto_id = ?
        """, (uid, produto_id))
        row = cursor.fetchone()

        if not row:
            cursor.execute("""
                INSERT INTO estoque (usuario_id, produto_id, quantidade, minimo)
                VALUES (?, ?, 0, 0)
            """, (uid, produto_id))
            conexao.commit()
            atual_qtd, atual_min = 0, 0
        else:
            atual_qtd, atual_min = row

        nova_qtd = atual_qtd + qtd if acao == "add" else atual_qtd - qtd
        if nova_qtd < 0:
            nova_qtd = 0

        if minimo_val is None:
            minimo_val = atual_min

        cursor.execute("""
            UPDATE estoque
            SET quantidade = ?, minimo = ?
            WHERE usuario_id = ? AND produto_id = ?
        """, (nova_qtd, minimo_val, uid, produto_id))

        conexao.commit()
        conexao.close()

        flash("Estoque atualizado ✅", "success")
        return redirect("/estoque")

    cursor.execute("""
        SELECT
            p.id,
            p.nome,
            p.preco,
            e.quantidade,
            e.minimo
        FROM produtos p
        LEFT JOIN estoque e
          ON e.produto_id = p.id AND e.usuario_id = p.usuario_id
        WHERE p.usuario_id = ?
        ORDER BY p.nome
    """, (uid,))
    itens = cursor.fetchall()
    conexao.close()

    return render_template("estoque.html", itens=itens)


# -----------------------------
# ERROS
# -----------------------------
@app.errorhandler(404)
def pagina_nao_encontrada(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def erro_interno(e):
    return render_template("500.html"), 500


if __name__ == "__main__":
    criar_banco()
    app.run(debug=True)
