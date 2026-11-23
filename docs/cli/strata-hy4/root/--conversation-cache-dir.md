# `strata-hy4 --serve --conversation-cache-dir`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4 --serve` |
| オプション | `--conversation-cache-dir` |
| 別名 | なし |
| 値 | ディレクトリパス（文字列） |

## 役割

`--serve` の会話キャッシュ保存先を指定します。キャッシュが有効になると、会話切替時に GPU 上の系列状態を指定ディレクトリへ保存し、後の要求で共通の token prefix を再利用できる状態を探します。これは常駐 RAM の `--session-reuse` とは別に、会話状態を SSD に退避して復元する仕組みです（`engine/src/hy4flash/run/hy4_main.hip.cpp:445`、`engine/src/hy4flash/run/hy4_serve.hip.h:365-370,455-493`、`engine/src/hy4flash/run/hy4_convcache.h:1-2`）。

## 使い方

```sh
strata-hy4 --serve --model ./model.strata --conversation-cache-dir ./conversation-cache
```

キャッシュ容量と保存対象の最低 token 数も調整する例です。

```sh
strata-hy4 --serve --model ./model.strata \
  --conversation-cache-dir ./conversation-cache \
  --conversation-cache-gib 20 --conversation-cache-min-tokens 2048
```

## 値と既定値

- 値は次の argv 要素から文字列として受け取り、CLI 側でパス形式や存在確認の事前 validation はしません。値を省略すると `ERR --conversation-cache-dir needs a value` を stdout に出して終了コード `2` で終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:376-383,445`）。
- 既定値は空文字列です。空のままなら cache を初期化せず無効です（`engine/src/hy4flash/run/hy4_main.hip.cpp:356-359`、`engine/src/hy4flash/run/hy4_serve.hip.h:50,365`）。
- 同じ引数を複数回指定すると、parser が `cc_dir` に順次代入するため最後の値が残ります（`engine/src/hy4flash/run/hy4_main.hip.cpp:445`）。

## 実行時の動作

`--serve` の設定にパスを渡し、cache 初期化時にディレクトリを作成します。初期化ではモデルファイルのサイズと basename、layer/ring 情報を読み取り、保存済みファイルを走査します。既定の容量予算は 40 GiB、保存対象の最低系列長は 1024 token です。`--conversation-cache-gib` と `--conversation-cache-min-tokens` で変更できます。最低系列長は内部で少なくとも 64 に補正されます（`engine/src/hy4flash/run/hy4_main.hip.cpp:356-359,445-447`、`engine/src/hy4flash/run/hy4_serve.hip.h:50-52,365-367`、`engine/src/hy4flash/run/hy4_convcache.h:70-103,165-166`）。

要求時に過去の cache に共通 prefix があり、常駐状態より 256 token を超えて有利な場合、保存済み系列を復元してそこから処理を再開します。現在の系列が別会話へ切り替わり、最低 token 数以上まで進んでいる場合は状態を退避します。キャッシュが有効なら `--session-reuse` を別途指定しなくても `reuse` が有効になります（`engine/src/hy4flash/run/hy4_serve.hip.h:367,455-493`）。画像を含む要求ではこの会話 cache の候補検索を行いません（同 `:470-472`）。

保存ファイル名は token 列から計算したキーに `.h4cc` を付けた形式で、書き込み時には一時ファイルを経由します。同じ保存先ファイルがあれば置き換え、既存のより短い prefix cache を削除する場合があります。容量予算を超えると最も古く使われた cache ファイルを削除します（`engine/src/hy4flash/run/hy4_convcache.h:188-218,221-235,318-326`）。起動時の走査では、保存ファイルのモデル名・サイズや ring などが現在と合わないファイル、破損ファイルを無視します。また、指定ディレクトリ直下の通常ファイルのうち `.tmp` で終わるものは削除します（同 `:420-450`）。

## 適用条件と副作用

- cache は `--serve` でのみ `ServeOpts` に渡され、サーバー初期化時に使われます。オフライン実行では parser が値を受け取りますが、cache 初期化へ渡す処理は確認できません（`engine/src/hy4flash/run/hy4_main.hip.cpp:445,517-577`）。
- 空パスなら初期化を呼び出さず cache は無効です。空でないパスでも容量 0、ディレクトリ作成失敗、モデルファイルのサイズ取得失敗、64 を超える layer 数などで初期化できない場合、cache を無効にしてサーバーを続行し、stderr に `[convcache] off: cannot use <path>` を出します（`engine/src/hy4flash/run/hy4_convcache.h:70-88`、`engine/src/hy4flash/run/hy4_serve.hip.h:365-366`）。
- cache 用ディレクトリとその中のファイルを作成・更新・削除します。保存先は cache 専用の空ディレクトリにするのが安全です。とくに起動時の `.tmp` 削除は、Strata が作成したファイルだけに限定する判定ではありません（`engine/src/hy4flash/run/hy4_convcache.h:194-218,420-426`）。
- このオプション文字列は Strata の CUDA/HIP `strata-hy4` parser にあります。Metal 版や SYCL 版への適用はこの調査範囲では確認していません（索引上のコマンド scope: `docs/cli/README.md:1279-1286`）。

## 出力とエラー

初期化成功時は stderr に cache の件数・使用量・予算・保存閾値を出します。初期化できなければ stderr に無効化メッセージを出して serve を継続します。保存失敗時は `[convcache] cannot write ...` または `[convcache] writing ... failed`、復元失敗時は理由と「prompt を読み直す」旨を stderr に出し、要求は prompt 全体を読む経路へ戻ります（`engine/src/hy4flash/run/hy4_convcache.h:101-103,195-219,239-278`、`engine/src/hy4flash/run/hy4_serve.hip.h:479-488`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:356-359,376-383,445,544-577` — CLI 変数の既定値、値取得、serve 分岐と設定への転送、値欠落時のエラー。
- `engine/src/hy4flash/run/hy4_serve.hip.h:50-52,365-370,455-493,607` — serve 内での初期化・無効化出力、再利用判定、park/restore 呼び出し。
- `engine/src/hy4flash/run/hy4_convcache.h:70-103,165-236,239-279,300-326,420-452` — 初期化条件、ディスク保存・復元、容量超過時削除、起動時ファイル走査と無視・削除条件。
