# Atualizações aplicadas (Fev/2026)

Este pacote já inclui as correções e melhorias abaixo:

## 1) Rotas corrigidas (evita 404)
- Clientes:
  - `GET/POST /clientes/<id>/editar`
  - `POST /clientes/<id>/excluir`
- Produtos:
  - `GET/POST /produtos/editar/<id>`
  - `POST /produtos/excluir/<id>`

Os templates `clientes.html` e `produtos.html` já apontam para essas rotas.

## 2) Segurança: marcar pedido como pago agora é POST
- `POST /marcar_pago/<id>`
O template `listar_pedidos.html` foi ajustado para enviar um formulário POST.

## 3) JavaScript: removido código duplicado de tema
O `static/app.js` tinha um segundo bloco de tema no final que podia causar conflito.
Agora fica apenas o controlador principal.

## 4) Organização
O antigo `app.py` (monolítico) foi renomeado para `app_legacy.py`.
A forma recomendada de rodar é usando `run.py`.

## Como rodar
1. Instale dependências:
   - `pip install -r requirements.txt`
2. Inicie:
   - `python run.py`
3. Acesse no navegador o endereço mostrado no terminal (geralmente `http://127.0.0.1:5000`).
