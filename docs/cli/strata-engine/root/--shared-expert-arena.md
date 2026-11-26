# `strata generate --shared-expert-arena`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（エンジン引数） |
| オプション | `--shared-expert-arena` |
| 別名 | なし |
| 値 | resident expert arena の共有 backing file のパス（Linux） |

## 役割

resident expert arena の backing にファイルの共有マッピングを使います。同じモデルを読む複数の engine process が同じ backing を指定すると、先行 process が expert を読み込み、後続 process はロード状態を見て読み込みを省略できます。help は Linux 用として説明し、`/dev/shm` 上のファイルを例示しています（`engine/src/program/generate.cpp:1483-1485`）。

## 使い方

```sh
# Linux: 同じ pack を使う複数の engine process に、同じ共有 backing のパスを渡す
strata generate --pack /path/to/pack --tokens "1,2,3" \
  --shared-expert-arena /dev/shm/strata-experts.bin
```

`--pack` と token 入力は generate の基本引数です。モデル・pack の指定方法に合わせて例を調整してください。

## 値と既定値

値は必須です。parser は次の argv 要素を文字列としてそのまま保存し、パス形式や空文字列の検証はしません。同じオプションを複数回指定した場合は後の値で置き換わります。未指定時は空文字列で、共有 backing を使わず通常の resident arena を確保します。値を省略すると stderr に `--shared-expert-arena needs a value` を出して終了コード 2 で終わります（`engine/src/program/generate.cpp:874,3842-3847,4217-4220`）。

## 実行時の動作

共有指定があると、arena の確保前に pack fingerprint を計算します。fingerprint は expert layout と pack metadata に加え、`experts.bin` または native pack の GGUF shard のサンプルを含みます（`engine/src/core/expert_source.cpp:6154-6189,6679-6681`）。

Linux では指定パスを `O_RDWR | O_CREAT` で開き、空ファイルなら arena サイズと 4 KiB header 分に拡張して、version・arena サイズ・pack fingerprint を記録します。既存ファイルは期待サイズと header、fingerprint が一致する必要があります。その後 `MAP_SHARED` で writable mapping を作り、arena はこの mapping の後半を使います。ファイルは自動削除されません。新規ファイルの作成 mode は `0600`（プロセスの umask の影響を受けます）です（`engine/src/core/pinned.cu:328-360,363-409,444-455`）。

共有状態 header の state word でロード担当を選びます。別 engine が読み込み中なら待ち、ロード完了済みなら読み込みを省略します。担当 process が終了した場合は別 process が再ロードし、待機が45分を超えた場合は自分でロードします（`engine/src/core/expert_source.cpp:6784-6819,6832-6843,6860`）。

## 適用条件と副作用

- `--mmap-experts` との併用は拒否されます。stderr に理由を出し、終了コード 2 です（`engine/src/program/generate.cpp:4866-4868`）。
- shared arena 指定時は、resident arena に対する通常の host available RAM / cgroup の事前判定を行いません。また RAM 不足時に `--mmap-experts` へ自動 fallback する条件からも除外されます。共有先が RAM に載る場合でも、既に共有されているページの有無をこの判定では数えません（`engine/src/core/expert_source.cpp:6530-6537`; `engine/include/strata/core/ple_residency.hpp:67-74`; `engine/src/program/generate.cpp:8602-8604`）。
- Linux の tmpfs では起動時に空き RAM と cgroup の余裕を確認し、確保可能な場合は `posix_fallocate` で領域を確保します。空きが足りない場合や mapping に失敗した場合は arena 確保失敗となります。通常のディスク上のファイルは sparse のままになり得るため、help は `/dev/shm` を推奨し、通常の SSD への配置を勧めていません（`engine/src/core/pinned.cu:412-454`; `engine/src/program/generate.cpp:1483-1485`）。
- shared backing を開けない、サイズ・header・pack fingerprint が合わない、または expert load に失敗した場合、engine は arena 初期化エラーを stderr に出し、終了コード 1 で終わります（`engine/src/core/pinned.cu:328-409,444-449`; `engine/src/core/expert_source.cpp:6760-6765,6848-6858`; `engine/src/program/generate.cpp:8913-8915`）。

## 出力とエラー

起動時には stderr に `expert arena: MAP_SHARED file ... (pack hash checked)` 相当の backing 情報とロード量を表示します。共有先が既にロード済みなら `already filled by another engine; the read is skipped` と表示します（`engine/src/core/pinned.cu:451-454`; `engine/src/core/expert_source.cpp:6832-6836`; `engine/src/program/generate.cpp:8934-8939`）。

## 根拠

- `engine/src/program/generate.cpp:1483-1485` — help の値・Linux 適用・`/dev/shm` 推奨。
- `engine/src/program/generate.cpp:874,4217-4220,3842-3847` — option の格納、parser、値不足時の処理。
- `engine/src/program/generate.cpp:4866-4868,8602-8604,8871-8872,8913-8915` — 併用拒否、fallback 判定、arena 呼び出しと失敗終了。
- `engine/src/core/expert_source.cpp:6154-6189,6679-6681` — pack fingerprint の構成と計算。
- `engine/src/core/pinned.cu:328-409,412-455,1030-1038` — Linux file 作成・header 検証・tmpfs 容量処理・`MAP_SHARED` と state word の配置。
- `engine/src/core/expert_source.cpp:6530-6537,6784-6819,6832-6858` — RAM 判定の省略、process 間のロード調停、load 失敗経路。
- `engine/include/strata/core/ple_residency.hpp:67-74` — shared arena 指定時に RAM fallback を許可しない条件。

調査範囲はこの checkout の `strata generate` parser と、その値を受ける CUDA expert arena 実装です。help は Linux の file path を説明しています。Windows の named section および SYCL 固有の挙動はこの文書の利用対象に含めていません。
