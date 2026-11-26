# `--batch-mtp`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジン、root 引数） |
| オプション | `--batch-mtp` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

`--serve` と `--batch` による複数リクエスト処理で、各 batch slot に MTP drafter を持たせ、各 slot の次 token と MTP 提案 token を同じ検証 window で検証します。提案が target の予測と一致すれば、上限や停止条件に反しない範囲で追加 token として採用します。既定では無効です。

## 使い方

```sh
# MTP runtime と speculative window を指定し、4 slot の server を起動する
strata --native MODEL.gguf --mtp DRAFT_RUNTIME --spec 4 --batch 4 --batch-mtp --serve
```

モデル・draft runtime のパスは利用環境に合わせてください。server は起動後、標準入力の要求を処理します。

## 値と既定値

- 引数値は取りません。parser は `--batch-mtp` を受けると boolean を true にします。複数回指定しても同じ true のままです（`engine/src/program/generate.cpp:4050`）。
- 既定値は off です（`engine/src/program/generate.cpp:1027`）。
- 環境変数 `STRATA_BATCH_MTP` でも有効化できます。未設定・空文字列・先頭文字が `0` の値は off、それ以外の非空値は on です。従って値を `false` としても off にはなりません（`engine/src/program/generate.cpp:7841-7842`）。

## 実行時の動作

- 有効化条件は `--batch 2` 以上、`--serve`、`--spec` 2 以上、および `--mtp` の指定です。条件を満たさない場合は標準エラーに warning を出して batch MTP を無効にし、可能なら通常の batch serving を続けます（`engine/src/program/generate.cpp:7843-7857`, `7870-7873`）。
- 起動時に slot ごとの `MtpDrafter` を作成し、MTP runtime を読み込んで各 drafter を準備します。slot drafter は solo drafter の重みを共有しますが、slot ごとの K/V state と buffer を確保します。GPU メモリを追加で消費し、確保または bind に失敗するとエンジン起動は失敗します（`engine/src/program/generate.cpp:8351-8379`, `13641-13660`）。
- 各 decode window では slot ごとに通常 token の行と提案行を verifier に渡します。提案を採用するのは target がその token を選び、停止 token・stop 条件・生成上限・context 上限に抵触しない場合です。採用行を commit し、slot ごとの提案数と採用数を記録します（`engine/src/program/generate.cpp:17119-17123`, `17175-17199`, `17260-17289`）。
- batch MTP の window は `kVerifyNarrowT` 行までです。各 slot が 2 行を使うため、上限を超える slot は window ごとに順番に処理されます。plain batching で使う広い window と異なるため、batch slot 数が多い場合も一度に全 slot を検証するわけではありません（`engine/src/program/generate.cpp:17119-17123`, `17175-17199`）。
- verifier の batch graph cache は上限 64 に設定されます（`engine/src/program/generate.cpp:13408-13413`, `13489-13497`）。

## 適用条件と相互作用

- layer split では各 stage が別 GPU にある構成が必要です。同じ GPU を共有する stage では無効になります。また、helper expert cache を使う layer split では無効になります（`engine/src/program/generate.cpp:7845-7848`, `7866-7869`）。
- Metal build では batch window が request ごとに 1 行を使い、提案行を検証できないため、この機能は無効になります。通常の batch は続行します（`engine/src/program/generate.cpp:7849-7856`）。
- layer split の pipelined `--batch-groups` は通常 batch MTP と両立せず、該当時は warning を出して slot drafts を実行しません。`STRATA_PIPED_MTP` を opt-in すると pipelined group でも提案を扱う別経路があります。serial window を選ぶには `--batch-groups 1` または `STRATA_BATCH_MTP_SERIAL=1` が使われます（`engine/src/program/generate.cpp:7812`, `7857-7865`, `7875-7884`, `17529-17547`）。
- Qwen3.6 family は共通 parser の後段ではなく family 専用 parser に振り分けられます（`engine/src/program/generate.cpp:3804-3818`）。索引上も同じ `--batch-mtp` は `strata-engine/qwen36/` の別 scope にあります。その parser では `--batch N` と `--mtp N` の要件・動作を個別に定義しているため、この文書の条件を適用しません（`engine/src/qwen35/q36_engine.cu:5383`, `5559-5560`、[索引](../../README.md)）。

## 出力とエラー

- 条件不成立時や pipelined group で提案を使えない場合、stderr に warning を出し、batch MTP を外して処理を続ける経路があります（`engine/src/program/generate.cpp:7870-7873`, `17543-17547`）。
- 起動時の slot drafter の load/bind や residual buffer 確保に失敗すると stderr に slot と理由を出し、終了コード 1 で終了します（`engine/src/program/generate.cpp:8362-8366`, `13645-13660`）。decode 中の drafter/commit 失敗は `ERR` 行を stdout に出し、batch 処理を失敗させます（`engine/src/program/generate.cpp:17274-17276`, `17377-17394`）。
- server の batch 統計出力では MTP 提案の採用数を stderr に出します（`engine/src/program/generate.cpp:17520-17523`）。

## 根拠

- `engine/src/program/generate.cpp:1027` — boolean の既定値。
- `engine/src/program/generate.cpp:1317-1323` — CLI help に記載された `--batch` / `--batch-mtp` の用途と概要。
- `engine/src/program/generate.cpp:4040-4056` — root parser での引数処理と関連する `--batch`、`--spec`、`--mtp`。
- `engine/src/program/generate.cpp:7841-7878` — 環境変数、有効化条件、無効化条件、pipelined MTP の選択。
- `engine/src/program/generate.cpp:8351-8379`, `13641-13660` — slot drafter の load/bind と VRAM 確保。
- `engine/src/program/generate.cpp:17119-17289`, `17377-17394` — decode window の行構成、提案採用、commit、失敗経路。
- `engine/src/program/generate.cpp:3804-3818`; `engine/src/qwen35/q36_engine.cu:5383`, `5559-5560` — Qwen3.6 family の別 parser への振り分けと別条件。
