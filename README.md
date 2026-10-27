# MangaDash para Tachimanga

Repositório pessoal gratuito de Gustavo, com uma compilação do MangaDash usando
a API legada **1.4**. O projeto é baseado no código Apache 2.0 do
[Keiyoushi](https://github.com/keiyoushi/extensions-source), sem afiliação oficial
com MangaDash, Tachimanga ou Keiyoushi.

## Correção do erro “Stub!” — versão 1.4.2

A publicação inicial usava a extensão 1.6.0, baseada na API nova `KeiSource`.
O Tachimanga pode chamar métodos da API legada, produzindo o erro “Stub!”.
Esta compilação utiliza `HttpSource` e implementa os métodos legados de catálogo,
busca, detalhes, capítulos e páginas. Os arquivos antigos já não estavam
 disponíveis nos downloads do upstream, então a versão legada foi recompilada.

O pacote agora tem assinatura própria deste repositório e mantém o mesmo
identificador de fonte: `4579000402227688678`.

### Se você instalou a versão 1.6.0

1. Desinstale **apenas a extensão MangaDash** no Tachimanga.
2. Remova e adicione novamente este repositório, para atualizar também a chave
   de assinatura. Isso é necessário caso o aplicativo mantenha a chave antiga.
3. Instale novamente o MangaDash, conferindo a versão **1.4.2**.
4. Abra a fonte e teste o catálogo, a busca, uma obra e um capítulo.

Não é necessário desinstalar o Tachimanga ou apagar sua biblioteca.
A execução completa no iPhone/iPad ainda precisa ser confirmada pelo usuário.

## Endereço do repositório

```text
https://raw.githubusercontent.com/2ksllvwr/-mangadash-tachimanga/main/index.pb
```

No Tachimanga, abra **Navegador → Extensões → Repositórios → Adicionar**.
Os nomes dos menus podem variar conforme a versão e o idioma do aplicativo.

Também é possível instalar manualmente o arquivo
`jar/tachiyomi-pt.mangadash-v1.4.2.jar`, usando o botão **+** da seção Extensões.
Os arquivos do pacote ficam hospedados neste próprio repositório, sem depender
de links antigos de downloads que possam desaparecer.

## Gratuidade e disponibilidade

A extensão não cobra assinatura e não inclui publicidade. Ela consulta a busca
e a paginação do MangaDash, sem restringir o catálogo a uma lista fixa de obras.
Nenhum mangá completo é hospedado neste repositório.

O acesso acompanha a disponibilidade do site: capítulos Premium, antecipados,
removidos ou sujeitos a login continuam com as condições da plataforma.
Anúncios e funções pagas do próprio Tachimanga são controlados pelo aplicativo.

Alguns capítulos são PDFs. O leitor original usa `android.graphics.pdf.PdfRenderer`;
sua execução depende do suporte dessa API no Tachimanga. A correção de
compatibilidade da API de extensões não substitui o teste desse recurso no iPhone.
Não há garantia de acesso a 100% do acervo nem de funcionamento de todos os PDFs.

## Como o pacote é produzido

- Código-fonte fixado em `d12e3b8a1eb5d7e5c7230f5b5b5854ba625a97dd`.
- Módulo original: `src/pt/mangadash`, ainda baseado em `HttpSource`/API 1.4.
- Alteração de compilação: `versionCode = 1` para `versionCode = 2`.
- O workflow **Compilar MangaDash legado** compila e executa `lintRelease`.
- A assinatura final é aplicada separadamente com a chave privada do proprietário.
  Somente o certificado público está incluído aqui; a chave privada não é publicada.
- O diretório `source/` contém o módulo e os metadados usados na compilação.
- `provenance.json` registra o commit e a execução de compilação.
- `release.json` registra a versão, a identidade da fonte e os hashes dos arquivos.

## Verificação automática

O workflow **Verificar MangaDash compatível** confere os arquivos locais e gera
os índices diariamente. Ele **não instala automaticamente versões novas do
upstream** e rejeita a API 1.6, evitando reintroduzir a incompatibilidade.

```bash
python3 -m unittest discover -s tests -v
python3 scripts/sync.py
```

Python 3.11 ou superior é suficiente, sem dependências externas. Os testes
verificam hashes, versões, identidade de 64 bits, certificado, índices e presença
dos métodos legados no JAR. As verificações locais não simulam o aplicativo iOS.

`index.pb` é protobuf comprimido com gzip; seu formato está em `schema/index.proto`.
Uma leitura independente usando o descritor oficial confirmou equivalência com
`index.json`. `SHA256SUMS` lista os hashes dos arquivos assinados.

## Licença

Apache 2.0, em `LICENSE`. Os créditos e as alterações estão em `NOTICE`.

Documentação do Tachimanga:
[extensões](https://tachimanga.app/help/guides/extensions.html) e
[repositórios](https://tachimanga.app/help/guides/repositories.html).
