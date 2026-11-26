# `strata --draft`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンの root 引数） |
| オプション | `--draft` |
| 別名 | なし |
| 値 | `mtp`、`dflash2`、`auto`（CUDA/HIP の `engine/src/program/generate.cpp`）。SYCL 実装は `mtp`、`dflash2` のみ |

## 役割

投機的デコードで候補トークンを提案する drafter を選びます。省略時および `mtp` は既存の MTP drafter を使います。CUDA/HIP では `dflash2` を選ぶと DFlash2 block drafter を使い、既定の fallback `none` では MTP 層をロードせず DFlash2 だけで動作します。`--draft-fallback mtp` を加えると両方をロードし、DFlash2 を開始できない場合に MTP を使います。`auto` は serve 専用の選択モードで、両 drafter を保持してリクエストごとに一方を使います。

## 使い方

```sh
# CUDA/HIP: MTP の代わりに DFlash2 を使う。--mtp は draft_vocab.bin の場所として必要。
strata --native model.gguf --tokens "1,2,3" --mtp ./mtp --spec 6 --draft dflash2 --draft-model ./dflash2-pack

# CUDA/HIP: DFlash2 を開始できない場合に MTP を fallback として残す。
strata --serve --native model.gguf --mtp ./mtp --spec 6 --draft dflash2 --draft-model ./dflash2-pack --draft-fallback mtp

# CUDA/HIP serve: リクエストの draft= 指定または --draft-rule に従って選ぶ。
strata --serve --native model.gguf --mtp ./mtp --spec 6 --draft auto --draft-model ./dflash2-pack

# SYCL: DFlash2 のみ。SYCL build は MTP 層との併用 fallback をサポートしない。
strata --native model.gguf --tokens "1,2,3" --mtp ./mtp --spec 6 --draft dflash2 --draft-model ./dflash2-q4-pack
```

`--tokens` は例を具体化するための入力です。実際には `--tokens-file` も使えます。通常の投機デコードには `--spec` が必要です。

## 値と既定値

- CUDA/HIP の parser は `--draft` の値を `mtp`、`dflash2`、`auto` に限定します。未指定時の値は空文字列で、通常の MTP 経路が使われます。明示的な `mtp` も同じ drafter を指定します。値が欠落した場合は共通の `next("--draft")` の引数処理に委ねられます。
- CUDA/HIP で `auto` を指定すると内部値を `dflash2` にし、`draft_auto` を有効にします。serve のリクエストに `draft=mtp|dflash2`（また `df2`）があればそれを使い、なければ `--draft-rule`（既定 `df2`）に従います。`learn` ルールはプロンプト先頭部分に基づいて選択を学習します。`auto` は両方の drafter を必要とし、複数 GPU の layer split または `--batch` と併用すると起動条件で拒否されます。
- `dflash2` は `--draft-model PACK`、`--spec` 2 以上、およびドラフト語彙ファイルを必要とします。語彙ファイルは `--mtp-draft-vocab FILE`、または `--mtp DIR` の `DIR/draft_vocab.bin` から解決されます。DFlash2 単独運用では `--mtp-draft-vocab` だけでも語彙ファイル指定として使えます。対応する native pack と DFlash2 対応 build も必要です。
- CUDA/HIP の `--draft-fallback` は `mtp` または `none`。省略時は空文字で、`dflash2` の非 auto 経路では `none` と同じ扱いです。`mtp` は MTP 層もロードし、DFlash2 が起動しないとき MTP へ切り替えます。`none` は MTP 層をロードしないため、DFlash2 が起動できなければ処理を続けられません。`auto` と `--draft-fallback none` の組み合わせはエラーです。
- SYCL parser では `mtp` と `dflash2` のみを受理します。`--draft-fallback` に指定できる値は `none` だけで、MTP 層と DFlash2 を併用する fallback はありません。

## 実行時の動作

CUDA/HIP では `--draft dflash2` の起動前検査で、既定の `none` 経路なら `--mtp` または `--mtp-draft-vocab`、`--spec >= 2`、`--draft-model` が必要です。`--mtp` はこの経路では MTP 層としてはクリアされますが、その `draft_vocab.bin` の場所として使われます。`--draft-fallback mtp` では `--mtp` が fallback の MTP 層と語彙ファイルを提供します。DFlash2 初期化は native pack、利用可能な taps、語彙、VRAM 等に依存します。通常の `dflash2` で DFlash2 が使えない場合は MTP へ fallback し、明示した `--draft-mtp-spec` があれば MTP 用に `--spec` を狭めます。DFlash2 単独経路では同じ失敗が起動エラーになります。

DFlash2 は verifier の taps から候補列を作り、verifier が候補を検証します。DFlash2 が選ばれて正常起動すると、カードに応じた window 上限が適用され、`--draft-cap` がある場合はその値が上限になります（この詳細は [`--draft-cap`](--draft-cap.md)）。DFlash2 を使えない理由として `--pipeline-windows` との非互換や native pack 不足などがあり、fallback の有無で「MTP に切り替える」か「起動を失敗させる」かが変わります。

SYCL は別 parser と実装を持ち、`--draft dflash2` でも MTP 層をロードしません。語彙ファイルと `--spec >= 2`、pack のほか、1 GPU・1 request の実行条件が検査されます。DFlash2 のロード失敗は起動エラーです。CUDA/HIP の起動・fallback 条件を SYCL に一般化できません。

## 適用条件と副作用

- この指定が候補提案に影響するのは投機デコード経路です。CUDA/HIP の MTP 層は `--spec < 2` では無視されます。DFlash2 では `--spec >= 2` が必須です。
- DFlash2 の pack と作業バッファ、draft head、K/V ring は GPU メモリを使います。CUDA/HIP のエラー案内は約 1.2 GiB を必要量の目安として示し、`--vram-reserve-mib` や小さな `--max-context` による調整を案内します。これは固定の保証値ではありません。
- CUDA/HIP `auto` は serve でのみ使う想定で、両 drafter を常駐させます。CUDA/HIP の自動 window cap はカードクラスにより変わり、指定した `--draft-cap` がある場合はそれを優先します。
- SYCL では parser が `--draft-fallback mtp` を拒否します。DFlash2 が起動できない場合に MTP へ切り替わる挙動はありません。

## 出力とエラー

- 未対応の `--draft` 値は stderr に `strata generate: --draft takes mtp, dflash2 or auto` を出し、終了コード 2 で終了します。`--draft-fallback` の不正値も stderr と終了コード 2 です。
- `auto` と `--draft-fallback none`、または DFlash2 単独に必要な pack・語彙・window の不足は起動検査で stderr に理由を出し、終了コード 2 になります。
- CUDA/HIP で fallback が `mtp`（または既定の fallback 経路）なら、DFlash2 を初期化できない理由を stderr に出して MTP を使います。`none` の単独経路では DFlash2 を初期化できないと stderr に理由を出し、終了コード 1 で終了します。
- SYCL で fallback 値が `none` 以外の場合は「only none is supported」と stderr に出して終了コード 2。DFlash2 の要件不足・起動失敗も stderr に出し、起動を終了します。

## 根拠

- `docs/cli/README.md:1036-1074` — `strata-engine`、root 引数の節、および `--draft` と関連 option の索引リンク。
- `engine/src/program/generate.cpp:1184-1197` — CUDA/HIP 側の option 状態と既定値に関する定義。
- `engine/src/program/generate.cpp:1361-1369` — root parser help に記載された drafter、fallback、serve auto の仕様。
- `engine/src/program/generate.cpp:4143-4163` — `--draft` / `--draft-fallback` の値変換と validation。
- `engine/src/program/generate.cpp:6494-6530` — `auto` と fallback の組み合わせ検査、DFlash2 単独の要件、MTP 層の解除。
- `engine/src/program/generate.cpp:8264-8326` — MTP/DFlash2 のロード、DFlash2 起動条件、window cap、起動失敗時の fallback と終了経路。
- `engine/src/program/generate.cpp:13584-13614` — serve 時の DFlash2 taps 準備、fallback、起動エラー。
- `engine/src/program/generate.cpp:18982-19005` — `auto` serve のリクエスト単位の drafter 選択。
- `engine/src/program/generate.cpp:24950-24991` — DFlash2 または MTP で候補列を作る実行経路。
- `engine/sycl/src/program/generate.cpp:785-789` — SYCL 側の DFlash2 と fallback 方針。
- `engine/sycl/src/program/generate.cpp:927-930` — SYCL build の help 上の option 条件。
- `engine/sycl/src/program/generate.cpp:2117-2126` — SYCL parser の `--draft` と fallback validation。
- `engine/sycl/src/program/generate.cpp:4499-4516` — SYCL 起動要件と `--draft` 値の validation。
- `engine/sycl/src/program/generate.cpp:4559-4563` — SYCL の実行制約および DFlash2 読み込み失敗経路。

調査範囲は同一 revision の Strata ソース内の CUDA/HIP root parser と別実装の SYCL parser・使用箇所です。GPU 実行を伴う pack 読み込み・メモリ量・backend ごとの実機動作は実測していません。
