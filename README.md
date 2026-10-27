# MangaDash para Tachimanga

Repositório pessoal gratuito que disponibiliza **somente a extensão MangaDash**
do projeto [Keiyoushi](https://github.com/keiyoushi/extensions-source).
O arquivo da extensão permanece original, com a assinatura do desenvolvedor.
Este projeto não é afiliado ao MangaDash, ao Tachimanga ou ao Keiyoushi.

## Instalar no iPhone ou iPad

Adicione o endereço do repositório no Tachimanga:

```text
https://raw.githubusercontent.com/2ksllvwr/-mangadash-tachimanga/main/index.pb
```

1. Atualize o Tachimanga pela App Store.
2. Abra **Navegador → Extensões → Repositórios** e adicione o endereço acima.
   O nome de alguns menus pode variar conforme o idioma e a versão do aplicativo.
3. Atualize a lista, procure **MangaDash** e instale a extensão.
4. Abra a fonte **MangaDash (Português do Brasil)**.

Também é possível instalar sem hospedar o repositório: extraia o ZIP no app
**Arquivos** e, no Tachimanga, abra **Navegador → Extensões → +**, selecionando
`jar/tachiyomi-pt.mangadash-v1.6.0.jar`. Se a versão mudar, escolha o `.jar`
mais recente dessa pasta. O `.apk` incluído serve para aplicativos Android.

Referência: [documentação de extensões](https://tachimanga.app/help/guides/extensions.html)
e [formato de repositório](https://tachimanga.app/help/guides/repositories.html).

## Gratuidade, catálogo e anúncios

- O repositório e a extensão não cobram assinatura, não inserem publicidade e
  não exigem servidor contratado. Os índices e arquivos podem ser hospedados
  em um repositório público gratuito do GitHub.
- A extensão consulta a busca e a paginação do site. Não há uma lista fixa de
  mangás dentro deste repositório, nem cópias dos mangás hospedadas aqui.
- O acesso segue a disponibilidade do MangaDash. Conteúdo Premium, antecipado,
  removido ou sujeito a login mantém as condições de acesso da plataforma.
- A extensão não executa os scripts de publicidade da página no leitor nativo.
  Anúncios e recursos pagos do próprio Tachimanga são controlados pelo aplicativo.
- Alguns capítulos são PDFs. A extensão original usa `android.graphics.pdf.PdfRenderer`;
  sua execução depende de essa API estar implementada na versão do Tachimanga.
  **O pacote foi conferido, mas a leitura no iPhone/iPad ainda precisa ser testada.**
  Não há garantia de compatibilidade integral nem de acesso a 100% do acervo.

## Repositório pessoal

Este pacote está configurado para o repositório público
`2ksllvwr/-mangadash-tachimanga`, na branch `main`.
O nome começa com um hífen; mantenha-o ao copiar o endereço.
A instalação inicial não depende de executar GitHub Actions.
Os downloads indicados no índice apontam para as versões originais do Keiyoushi.

Se usar outro nome de repositório ou outra conta, ajuste `repository.json`,
execute `python3 scripts/sync.py` e use o endereço retornado em `repo.json`.

## Atualizações e desenvolvimento

O fluxo **Actions → Atualizar MangaDash** consulta o projeto original diariamente
e também pode ser executado manualmente. Usa apenas Python 3.11 ou superior,
sem dependências externas e sem token pessoal. O token automático do GitHub
precisa de permissão de escrita em conteúdo; políticas da conta podem restringi-lo.
Agendamentos podem sofrer atrasos ou ser desativados por inatividade pelo GitHub.

```bash
python3 -m unittest discover -s tests -v
python3 scripts/sync.py
```

O sincronizador usa um único commit imutável do upstream para ler `index.json`,
`index.pb` e as somas SHA-256. Ele mantém apenas o pacote
`eu.kanade.tachiyomi.extension.pt.mangadash`, preserva seu identificador de fonte,
confere a chave de assinatura esperada e verifica os arquivos baixados antes de
atualizar os índices. Mudanças na chave de assinatura exigem revisão manual.
Não usa o antigo `index.min.json`, que atualmente mostra avisos de aplicativo
desatualizado no upstream.

`provenance.json` identifica o commit do índice, o código-fonte correspondente e
as origens dos arquivos. `SHA256SUMS` registra as somas de verificação locais.
`schema/index.proto` documenta o formato original. Os scripts deste projeto
filtram e distribuem uma extensão pronta; não constituem um ambiente completo
para recompilar o código Kotlin. Para modificá-lo, use o projeto original
referenciado em `provenance.json`.

## Licença e créditos

Distribuição sob a licença Apache 2.0, incluída em `LICENSE`. Os créditos e a
distinção entre o pacote original e os arquivos adicionados estão em `NOTICE`.
